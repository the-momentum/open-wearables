import json
import shutil
import sqlite3
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from app.services.providers.gadgetbridge.automatic import AutomaticImporter, snapshot

USER = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def database(tmp_path: Path) -> Path:
    path = tmp_path / "Gadgetbridge.db"
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE DEVICE (_id INTEGER, IDENTIFIER TEXT, MODEL TEXT);
            INSERT INTO DEVICE VALUES (1,'synthetic-device','Huawei Band test');
            CREATE TABLE HUAWEI_ACTIVITY_SAMPLE (TIMESTAMP INTEGER, OTHER_TIMESTAMP INTEGER, SOURCE INTEGER,
                DEVICE_ID INTEGER, USER_ID INTEGER, STEPS INTEGER, DISTANCE INTEGER, HEART_RATE INTEGER,
                SPO INTEGER, CALORIES INTEGER);
            INSERT INTO HUAWEI_ACTIVITY_SAMPLE VALUES (1791320400,1791320460,11,1,1,42,20,65,98,500);
        """)
    return path


class WorkerAPI:
    def __init__(self) -> None:
        self.runs: dict[str, dict] = {}
        self.posts = 0
        self.fail = False
        self.lose_response = False
        self.api_status = 200

    def handle(self, request: httpx.Request) -> httpx.Response:
        if self.api_status != 200:
            return httpx.Response(self.api_status)
        if request.url.path.endswith("/sync"):
            self.posts += 1
            payload = json.loads(request.content)
            data = payload["data"]
            self.runs[payload["syncSessionId"]] = {
                "run_id": "sdk_" + payload["syncSessionId"],
                "user_id": USER,
                "provider": "gadgetbridge",
                "status": "failed" if self.fail else "success",
                "items_processed": sum(map(len, data.values())),
            }
            if self.lose_response:
                raise httpx.ReadError("Synthetic lost acceptance response")
            return httpx.Response(202)
        if request.url.path.endswith("/logs"):
            return httpx.Response(200)
        return httpx.Response(200, json=list(self.runs.values()))


def test_settling_unchanged_exports_and_restarts_do_not_resubmit(database: Path, tmp_path: Path) -> None:
    api = WorkerAPI()
    state = tmp_path / "state"
    with httpx.Client(base_url="http://app:8000", transport=httpx.MockTransport(api.handle)) as client:
        importer = AutomaticImporter(database, state, client, USER, settle_seconds=30)
        assert importer.step(100) == "waiting_for_stable_file"
        assert importer.step(129) == "waiting_for_stable_file"
        assert api.posts == 0
        assert importer.step(130) == "confirmed"
        with patch("app.services.providers.gadgetbridge.automatic.snapshot", side_effect=AssertionError("No recopy")):
            assert importer.step(160) == "unchanged"
        restarted = AutomaticImporter(database, state, client, USER, settle_seconds=0)
        assert restarted.step(200) == "unchanged"
    assert api.posts == 1
    assert not list(state.glob("snapshot-*.db"))
    assert not list(state.glob("jobs/*/payloads.json"))
    assert (state / "status.json").stat().st_mode & 0o777 == 0o600


def test_new_complete_export_is_detected_without_requiring_a_new_filename(database: Path, tmp_path: Path) -> None:
    api = WorkerAPI()
    with httpx.Client(base_url="http://app:8000", transport=httpx.MockTransport(api.handle)) as client:
        importer = AutomaticImporter(database, tmp_path / "state", client, USER, settle_seconds=0)
        assert importer.step(100) == "confirmed"
        with sqlite3.connect(database) as connection:
            connection.execute("INSERT INTO HUAWEI_ACTIVITY_SAMPLE VALUES (1791320460,1791320520,11,1,1,7,3,70,98,50)")
        assert importer.step(200) == "confirmed"
        assert importer.step(300) == "unchanged"
    assert api.posts == 2


def test_partial_transfer_never_posts_and_new_valid_export_recovers(database: Path, tmp_path: Path) -> None:
    original = database.read_bytes()
    database.write_bytes(original[:100])
    api = WorkerAPI()
    state = tmp_path / "state"
    with httpx.Client(base_url="http://app:8000", transport=httpx.MockTransport(api.handle)) as client:
        importer = AutomaticImporter(database, state, client, USER, settle_seconds=0, retry_seconds=10)
        with pytest.raises(sqlite3.Error):
            importer.step(100)
        assert api.posts == 0
        assert importer.step(105) == "retry_wait"
        database.write_bytes(original)
        assert importer.step(110) == "confirmed"
    assert not list(state.glob("snapshot-*.db"))


def test_lost_http_response_is_reconciled_after_restart_without_another_post(database: Path, tmp_path: Path) -> None:
    api = WorkerAPI()
    api.lose_response = True
    state = tmp_path / "state"
    with httpx.Client(base_url="http://app:8000", transport=httpx.MockTransport(api.handle)) as client:
        importer = AutomaticImporter(database, state, client, USER, settle_seconds=0, retry_seconds=10)
        with pytest.raises(httpx.ReadError):
            importer.step(100)
        status = json.loads((state / "status.json").read_text())
        assert "confirmed_sha256" not in status
        assert status["pending"]["attempts"] == 1
        api.lose_response = False
        restarted = AutomaticImporter(database, state, client, USER, settle_seconds=0, retry_seconds=10)
        assert restarted.step(110) == "confirmed"
    assert api.posts == 1


def test_failed_pending_export_is_finished_before_new_incoming_data(database: Path, tmp_path: Path) -> None:
    api = WorkerAPI()
    api.fail = True
    state = tmp_path / "state"
    with httpx.Client(base_url="http://app:8000", transport=httpx.MockTransport(api.handle)) as client:
        importer = AutomaticImporter(database, state, client, USER, settle_seconds=0, retry_seconds=10, timeout=1)
        with pytest.raises(RuntimeError):
            importer.step(100)
        with sqlite3.connect(database) as connection:
            connection.execute("INSERT INTO HUAWEI_ACTIVITY_SAMPLE VALUES (1791320460,1791320520,11,1,1,7,3,70,98,50)")
        api.fail = False
        restarted = AutomaticImporter(database, state, client, USER, settle_seconds=0, retry_seconds=10, timeout=1)
        assert restarted.step(110) == "confirmed"
        assert restarted.step(111) == "confirmed"
    assert api.posts == 3
    assert list(api.runs.values())[-1]["items_processed"] == 10


def test_api_rejection_retains_pending_data_without_confirming(database: Path, tmp_path: Path) -> None:
    api = WorkerAPI()
    api.api_status = 401
    state = tmp_path / "state"
    with httpx.Client(base_url="http://app:8000", transport=httpx.MockTransport(api.handle)) as client:
        importer = AutomaticImporter(database, state, client, USER, settle_seconds=0)
        with pytest.raises(httpx.HTTPStatusError):
            importer.step(100)
    status = json.loads((state / "status.json").read_text())
    assert "pending" in status
    assert "confirmed_sha256" not in status
    assert list(state.glob("jobs/*/payloads.json"))


def test_missing_file_and_temporary_syncthing_file_are_not_imported(tmp_path: Path) -> None:
    (tmp_path / ".syncthing.Gadgetbridge.db.tmp").write_bytes(b"incomplete")
    with httpx.Client(base_url="http://app:8000") as client:
        importer = AutomaticImporter(tmp_path / "Gadgetbridge.db", tmp_path / "state", client, USER)
        assert importer.step(100) == "waiting_for_export"


@pytest.mark.parametrize("change", [{"user_id": "another-user"}, {"timezone_name": "UTC"}, {"batch_size": 100}])
def test_persistent_state_cannot_be_reused_for_another_target(database: Path, tmp_path: Path, change: dict) -> None:
    api = WorkerAPI()
    state = tmp_path / "state"
    with httpx.Client(base_url="http://app:8000", transport=httpx.MockTransport(api.handle)) as client:
        AutomaticImporter(database, state, client, USER, settle_seconds=0).step(100)
        with pytest.raises(ValueError, match="another user"):
            AutomaticImporter(database, state, client, **{"user_id": USER, **change})


def test_live_database_and_symlinks_are_rejected(database: Path, tmp_path: Path) -> None:
    Path(str(database) + "-wal").write_bytes(b"live database")
    with pytest.raises(ValueError, match="WAL"):
        snapshot(database, tmp_path)
    Path(str(database) + "-wal").unlink()
    link = tmp_path / "link.db"
    link.symlink_to(database)
    with pytest.raises(ValueError, match="symlink"):
        snapshot(link, tmp_path)


def test_input_replaced_during_snapshot_is_rejected(database: Path, tmp_path: Path) -> None:
    real_read = Path.lstat
    calls = 0

    def replace_on_second_read(path: Path) -> object:
        nonlocal calls
        if path == database:
            calls += 1
            if calls == 2:
                replacement = tmp_path / "replacement.db"
                shutil.copyfile(database, replacement)
                replacement.replace(database)
        return real_read(path)

    with patch.object(Path, "lstat", replace_on_second_read), pytest.raises(ValueError, match="replaced"):
        snapshot(database, tmp_path)
    assert not list(tmp_path.glob("snapshot-*.db"))

import json
import sqlite3
from datetime import datetime
from pathlib import Path

import httpx
import pytest

from app.services.providers.gadgetbridge.export import HuaweiExport, batches
from app.services.providers.gadgetbridge.upload import upload_batches


def epoch(value: str, milliseconds: bool = False) -> int:
    return int(datetime.fromisoformat(value).timestamp() * (1000 if milliseconds else 1))


@pytest.fixture
def database(tmp_path: Path) -> Path:
    path = tmp_path / "synthetic.sqlite"
    start = epoch("2026-10-06T21:00:00+00:00")
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE DEVICE (_id INTEGER, IDENTIFIER TEXT, MODEL TEXT);
            INSERT INTO DEVICE VALUES (1, 'test-band', 'Huawei Band test');
            CREATE TABLE HUAWEI_ACTIVITY_SAMPLE (TIMESTAMP INTEGER, OTHER_TIMESTAMP INTEGER, SOURCE INTEGER,
                DEVICE_ID INTEGER, USER_ID INTEGER, STEPS INTEGER, DISTANCE INTEGER, HEART_RATE INTEGER,
                RESTING_HEART_RATE INTEGER, SPO INTEGER, CALORIES INTEGER);
            CREATE TABLE HUAWEI_HRV_VALUE_SAMPLE (TIMESTAMP INTEGER, LAST_TIMESTAMP INTEGER,
                DEVICE_ID INTEGER, VALUE INTEGER);
            CREATE TABLE HUAWEI_SLEEP_STAGE_SAMPLE (TIMESTAMP INTEGER, DEVICE_ID INTEGER, STAGE INTEGER);
            CREATE TABLE HUAWEI_SLEEP_STATS_SAMPLE (DEVICE_ID INTEGER, TIMESTAMP INTEGER,
                BED_TIME INTEGER, WAKEUP_TIME INTEGER);
            CREATE TABLE HUAWEI_WORKOUT_SUMMARY_SAMPLE (WORKOUT_ID INTEGER, DEVICE_ID INTEGER, START_TIMESTAMP INTEGER,
                END_TIMESTAMP INTEGER, DISTANCE INTEGER, STEP_COUNT INTEGER, CALORIES INTEGER, TYPE INTEGER);
        """)
        connection.execute(
            "INSERT INTO HUAWEI_ACTIVITY_SAMPLE VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (start, start + 60, 11, 1, 1, 42, 20, -126, -1, 98, 500),
        )
        connection.execute(
            "INSERT INTO HUAWEI_ACTIVITY_SAMPLE VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (start + 60, start, 11, 1, 1, -1, -1, -1, -1, -1, -1),
        )
        connection.execute(
            "INSERT INTO HUAWEI_HRV_VALUE_SAMPLE VALUES (?,?,?,?)", (start * 1000, (start + 300) * 1000, 1, 38)
        )
        connection.execute(
            "INSERT INTO HUAWEI_SLEEP_STATS_SAMPLE VALUES (?,?,?,?)",
            (1, start * 1000, start * 1000, (start + 240) * 1000),
        )
        for index, stage in enumerate([1, 2, 3, 4]):
            connection.execute(
                "INSERT INTO HUAWEI_SLEEP_STAGE_SAMPLE VALUES (?,?,?)", ((start + index * 60) * 1000, 1, stage)
            )
        connection.execute(
            "INSERT INTO HUAWEI_WORKOUT_SUMMARY_SAMPLE VALUES (?,?,?,?,?,?,?,?)",
            (1, 1, start, start + 120, 20, 42, 2, -33),
        )
    return path


def test_verified_huawei_units_stages_hrv_and_signed_sensor_byte(database: Path) -> None:
    before = database.read_bytes()
    exporter = HuaweiExport(database)
    data = exporter.convert()
    metrics = {row["type"]: row for row in data["records"]}
    assert metrics["STEP_COUNT"]["value"] == 42
    assert metrics["DISTANCE"]["value"] == 20
    assert metrics["HEART_RATE"]["value"] == 130
    assert "RESTING_HEART_RATE" not in metrics
    assert metrics["ACTIVE_CALORIES_BURNED"]["value"] == 0.5
    assert metrics["HEART_RATE_VARIABILITY"]["value"] == 38
    assert metrics["HEART_RATE_VARIABILITY"]["startDate"] == metrics["HEART_RATE_VARIABILITY"]["endDate"]
    assert [row["stage"] for row in data["sleep"]] == ["light", "rem", "deep", "awake"]
    assert data["workouts"][0]["type"] == "other"
    assert data["workouts"][0]["values"][-1] == {"type": "activeEnergyBurned", "unit": "kcal", "value": 2}
    assert all(row["value"] >= 0 for row in data["records"])
    assert exporter.report["non_measurement_rows"] == 1
    assert database.read_bytes() == before
    assert exporter.convert() == data
    assert sum(len(payload["data"][key]) for payload in batches(data, 2) for key in data) == sum(
        map(len, data.values())
    )


def test_dst_and_mixed_epoch_units(database: Path) -> None:
    exporter = HuaweiExport(database)
    before = epoch("2026-10-25T00:30:00+00:00")
    after = epoch("2026-10-25T01:30:00+00:00")
    assert exporter.timestamp(before)[1] == "+02:00"
    assert exporter.timestamp(after * 1000, True)[1] == "+01:00"
    assert exporter.timestamp(before * 1000, True) == exporter.timestamp(before)
    with pytest.raises(ValueError, match="epoch"):
        exporter.timestamp(before * 1000)


def test_invalid_values_and_sleep_gaps_are_not_filled(database: Path) -> None:
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE HUAWEI_ACTIVITY_SAMPLE SET HEART_RATE=-1,SPO=101 WHERE OTHER_TIMESTAMP>TIMESTAMP")
        connection.execute("DELETE FROM HUAWEI_SLEEP_STAGE_SAMPLE WHERE STAGE IN (2,3)")
    exporter = HuaweiExport(database)
    data = exporter.convert()
    assert not {"HEART_RATE", "OXYGEN_SATURATION"} & {row["type"] for row in data["records"]}
    assert exporter.report["sleep_gaps"] == 1
    assert (
        sum(
            (datetime.fromisoformat(row["endDate"]) - datetime.fromisoformat(row["startDate"])).total_seconds()
            for row in data["sleep"]
        )
        == 120
    )


def test_unknown_stage_and_conflicting_samples_fail_explicitly(database: Path) -> None:
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE HUAWEI_SLEEP_STAGE_SAMPLE SET STAGE=99 WHERE STAGE=1")
    with pytest.raises(ValueError, match="every observed code"):
        HuaweiExport(database).convert()
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE HUAWEI_SLEEP_STAGE_SAMPLE SET STAGE=1 WHERE STAGE=99")
        connection.execute("""INSERT INTO HUAWEI_ACTIVITY_SAMPLE SELECT TIMESTAMP, OTHER_TIMESTAMP, SOURCE, DEVICE_ID,
                           USER_ID, STEPS+1,DISTANCE,HEART_RATE,RESTING_HEART_RATE,SPO,CALORIES
                           FROM HUAWEI_ACTIVITY_SAMPLE WHERE OTHER_TIMESTAMP>TIMESTAMP""")
    with pytest.raises(ValueError, match="Conflicting"):
        HuaweiExport(database).convert()


def test_multiple_users_require_selection(database: Path) -> None:
    with sqlite3.connect(database) as connection:
        connection.execute("""INSERT INTO HUAWEI_ACTIVITY_SAMPLE SELECT TIMESTAMP+120, OTHER_TIMESTAMP+120, SOURCE,
                           DEVICE_ID,2,STEPS,DISTANCE,HEART_RATE,RESTING_HEART_RATE,SPO,CALORIES
                           FROM HUAWEI_ACTIVITY_SAMPLE WHERE OTHER_TIMESTAMP>TIMESTAMP""")
    with pytest.raises(ValueError, match="multiple users"):
        HuaweiExport(database).convert()
    assert HuaweiExport(database, gadgetbridge_user_id=1).convert()["records"]


@pytest.mark.parametrize("outcome", ["success", "failed", "timeout", "partial"])
def test_checkpoint_waits_for_worker_and_resume_does_not_resend_verified(tmp_path: Path, outcome: str) -> None:
    payload = {"provider": "gadgetbridge", "data": {"records": [{"type": "STEP_COUNT"}], "sleep": [], "workouts": []}}
    session = ""
    posts = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal session
        if request.method == "POST":
            posts.append(request.url.path)
            raw = json.loads(request.content)
            session = raw["syncSessionId"]
            return httpx.Response(202, json={})
        return httpx.Response(
            200,
            json=[
                {
                    "run_id": "sdk_" + session,
                    "status": outcome,
                    "provider": "gadgetbridge",
                    "user_id": "test-user",
                    "items_processed": 1,
                }
            ],
        )

    checkpoint = tmp_path / "checkpoint.json"
    with httpx.Client(base_url="http://localhost", transport=httpx.MockTransport(handler)) as client:
        if outcome == "success":
            assert upload_batches(client, "test-user", [payload], checkpoint) == 1
            assert upload_batches(client, "test-user", [payload], checkpoint) == 1
            assert len(posts) == 2  # one data request and one type-completion log; no resumed repost
        else:
            with pytest.raises((RuntimeError, TimeoutError)):
                upload_batches(client, "test-user", [payload], checkpoint, timeout=0 if outcome == "timeout" else 1)
            assert not json.loads(checkpoint.read_text())["batches"]["0"]["verified"]
            timed_out = outcome == "timeout"
            outcome = "success"
            assert upload_batches(client, "test-user", [payload], checkpoint, retry_unconfirmed=not timed_out) == 1
            # A pending accepted request is reconciled; failed requests require an explicit retry.
            assert len(posts) == (2 if timed_out else 3)
    assert checkpoint.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize(
    "confirmation",
    [
        {"items_processed": 0},
        {"message": "1 dropped record"},
        {"provider": "health_connect"},
        {"user_id": "another-user"},
    ],
)
def test_inconsistent_worker_confirmation_is_never_checkpointed(tmp_path: Path, confirmation: dict) -> None:
    payload = {"provider": "gadgetbridge", "data": {"records": [{"type": "STEP_COUNT"}], "sleep": [], "workouts": []}}
    session = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal session
        if request.method == "POST":
            session = json.loads(request.content)["syncSessionId"]
            return httpx.Response(202)
        return httpx.Response(
            200,
            json=[
                {
                    "run_id": "sdk_" + session,
                    "status": "success",
                    "provider": "gadgetbridge",
                    "user_id": "test-user",
                    "items_processed": 1,
                    **confirmation,
                }
            ],
        )

    checkpoint = tmp_path / "checkpoint.json"
    with (
        httpx.Client(base_url="http://localhost", transport=httpx.MockTransport(handler)) as client,
        pytest.raises(RuntimeError),
    ):
        upload_batches(client, "test-user", [payload], checkpoint)
    assert not json.loads(checkpoint.read_text())["batches"]["0"]["verified"]

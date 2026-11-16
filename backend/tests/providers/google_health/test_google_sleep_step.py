"""Regression: the sleep step must not wrap ``create_or_merge_sleep`` in a savepoint.

``event_record_service.create_or_merge_sleep`` commits the session itself on every
re-ingested sleep record. Inside ``run.step(..., savepoint=True)`` that inner commit
closed the step's nested transaction, so the next statement — or the context exit —
raised ``sqlalchemy.exc.InvalidRequestError`` and every pull re-reading a known
session (guaranteed by the lookback window) failed ``sleep`` and reported ``partial``.
The step lets the handler own commits now; this test runs the whole
``load_and_save_all`` with a fetch stub that commits mid-step, which is exactly what
production did.
"""

from datetime import datetime, timedelta, timezone
from typing import cast
from unittest.mock import MagicMock, patch
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.schemas.enums.data_granularity import DataGranularity
from app.services.providers.google_health.data_247 import GoogleHealth247Data

USER_ID = str(uuid4())
API = "https://health.googleapis.com"
END = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)
START = END - timedelta(days=2)


def _data_247() -> GoogleHealth247Data:
    data = GoogleHealth247Data(oauth=MagicMock(), connection_repo=MagicMock(), api_base_url=API)
    data.settings_repo = MagicMock()
    data.settings_repo.get_data_granularity.return_value = DataGranularity.RAW
    data.sleep = MagicMock()
    return data


def _self_committing_load_and_save(db: Session, user_id: str, start: datetime, end: datetime) -> int:
    """What ``sleep.load_and_save`` does to the session on a re-ingested record.

    The merge handler commits, then the record loop emits the next statement —
    the second part is what blows up under a savepoint.
    """
    db.commit()
    db.execute(text("SELECT 1"))
    return 1


class TestSleepStepCommits:
    def test_handler_commit_does_not_fail_the_sleep_step(self, session_factory: sessionmaker[Session]) -> None:
        # A plain session: the ``db`` fixture's savepoint-restart listener would hide
        # the closed-transaction error this test guards against.
        db = session_factory()
        data = _data_247()
        cast(MagicMock, data.sleep).load_and_save.side_effect = _self_committing_load_and_save

        with (
            patch.object(data, "_scope_granted", return_value=False),
            patch.object(data, "_native_samples", return_value=[]),
            patch.object(data, "_rollup_samples", return_value=[]),
            patch.object(data, "_derived_daily_samples", return_value=[]),
            patch.object(data, "_daily_rollup_samples", return_value=[]),
        ):
            result = data.load_and_save_all(db, USER_ID, START, END)

        assert "sleep" in result.synced
        assert "sleep" not in result.failures

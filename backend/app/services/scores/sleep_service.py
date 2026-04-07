"""Sleep score service.

Exposes two entry points for computing a per-night OW sleep score using the
four-pillar algorithm (duration, stages, consistency, interruptions):

- SleepScoreService.get_sleep_score   – pure calculation; accepts raw sleep parameters
- SleepScoreService.get_sleep_score_for_user – DB-backed; fetches data from the database
"""

from datetime import date, datetime, timedelta
from logging import Logger, getLogger
from uuid import UUID

from pydantic import BaseModel

from app.algorithms.config_algorithms import sleep_config
from app.algorithms.sleep import SleepScoreResult, calculate_overall_sleep_score
from app.database import DbSession
from app.models import EventRecord, SleepDetails
from app.repositories.event_record_repository import EventRecordRepository
from app.schemas.model_crud.activities import EventRecordQueryParams
from app.utils.exceptions import ResourceNotFoundError, handle_exceptions


class WasoData(BaseModel):
    total_awake_minutes: float
    awakening_durations: list[float]


class SleepScoreService:
    """Service for computing per-night sleep scores."""

    def __init__(self, log: Logger):
        self.logger = log
        self.event_record_repo = EventRecordRepository(EventRecord)

    def _convert_stages_to_duration_blocks(
        self,
        raw_stages_json: list[dict[str, str]],
    ) -> list[dict[str, str | float]]:
        """Convert start_time/end_time stage blocks to duration_mins format.

        Input:  [{"stage": "...", "start_time": "...", "end_time": "..."}, ...]
        Output: [{"stage": "...", "duration_mins": float}, ...]
        """
        result: list[dict[str, str | float]] = []
        for block in raw_stages_json:
            start = datetime.fromisoformat(block["start_time"].rstrip("Z"))
            end = datetime.fromisoformat(block["end_time"].rstrip("Z"))
            duration_mins = (end - start).total_seconds() / 60.0
            result.append({"stage": block["stage"], "duration_mins": duration_mins})
        return result

    def _parse_wearable_stages_for_interruptions(
        self,
        raw_stage_blocks: list[dict[str, str | float]],
    ) -> WasoData:
        """Strip sleep latency and morning lying-in-bed periods to calculate true WASO.

        Expected input: [{"stage": "awake"|"light"|..., "duration_mins": float}, ...]
        Returns total WASO minutes and individual awakening durations.
        """
        if not raw_stage_blocks:
            return WasoData(total_awake_minutes=0.0, awakening_durations=[])

        first_sleep_idx = next(
            (i for i, b in enumerate(raw_stage_blocks) if str(b["stage"]).lower() != "awake"),
            None,
        )
        if first_sleep_idx is None:
            return WasoData(total_awake_minutes=0.0, awakening_durations=[])

        last_sleep_idx = next(
            (
                i
                for i in range(len(raw_stage_blocks) - 1, -1, -1)
                if str(raw_stage_blocks[i]["stage"]).lower() != "awake"
            ),
            None,
        )

        true_sleep_period = raw_stage_blocks[first_sleep_idx : last_sleep_idx + 1]  # type: ignore[operator]

        waso_total_minutes = 0.0
        awakening_durations: list[float] = []
        for block in true_sleep_period:
            if str(block["stage"]).lower() == "awake":
                waso_total_minutes += float(block["duration_mins"])
                awakening_durations.append(float(block["duration_mins"]))

        return WasoData(
            total_awake_minutes=waso_total_minutes,
            awakening_durations=awakening_durations,
        )

    def get_sleep_score(
        self,
        total_sleep_duration_minutes: float,
        deep_minutes: float,
        rem_minutes: float,
        awake_minutes: float,
        session_start: datetime,
        historical_bedtimes: list[datetime],
        sleep_stages: list[dict[str, str]] | None = None,
    ) -> SleepScoreResult:
        """Calculate a sleep score from raw sleep parameters for a single night.

        If sleep_stages is provided it is used to derive true WASO (strips sleep
        latency and morning lie-in). Otherwise awake_minutes is used as a fallback
        for interruption scoring.

        total_sleep_duration_minutes is expected to be net sleep (awake time already
        excluded), as stored by wearable providers. awake_minutes / stage-derived WASO
        feeds only the interruptions pillar.
        """
        if not total_sleep_duration_minutes or total_sleep_duration_minutes <= 0:
            raise ValueError(
                "Cannot calculate sleep score: total_sleep_duration_minutes must be"
                f" > 0, got {total_sleep_duration_minutes}"
            )

        if sleep_stages:
            duration_blocks = self._convert_stages_to_duration_blocks(sleep_stages)
            waso = self._parse_wearable_stages_for_interruptions(duration_blocks)
            total_awake = waso.total_awake_minutes
            awakening_durations = waso.awakening_durations
        else:
            total_awake = awake_minutes
            awakening_durations = []

        net_sleep_minutes = total_sleep_duration_minutes

        return calculate_overall_sleep_score(
            total_sleep_minutes=net_sleep_minutes,
            deep_minutes=deep_minutes,
            rem_minutes=rem_minutes,
            session_start=session_start.isoformat(),
            historical_bedtimes=[dt.isoformat() for dt in historical_bedtimes],
            total_awake_minutes=total_awake,
            awakening_durations=awakening_durations,
        )

    @handle_exceptions
    def get_sleep_score_for_user(
        self,
        db_session: DbSession,
        user_id: UUID,
        sleep_date: date,
    ) -> SleepScoreResult:
        """Fetch sleep data for a user on a given date and return their sleep score.

        sleep_date is the calendar date on which the sleep session started (bedtime
        date). The longest non-nap session that started on that date is used.
        Historical bedtimes from the prior rolling window are fetched for consistency
        scoring.
        """
        day_start = datetime(sleep_date.year, sleep_date.month, sleep_date.day)

        # Fetch sessions that started on sleep_date (broader window, post-filter below).
        records, _ = self.event_record_repo.get_records_with_filters(
            db_session,
            EventRecordQueryParams(
                category="sleep",
                start_datetime=day_start,
                sort_by="start_datetime",
                sort_order="asc",
                limit=20,
            ),
            str(user_id),
        )

        # Keep non-nap sessions that actually started on sleep_date.
        sessions = [
            (record, detail)
            for record, _ in records
            if record.start_datetime.date() == sleep_date
            and isinstance((detail := record.detail), SleepDetails)
            and not detail.is_nap
        ]

        if not sessions:
            raise ResourceNotFoundError(f"sleep data for user {user_id} on {sleep_date}")

        record, detail = max(sessions, key=lambda s: s[1].sleep_total_duration_minutes or 0)

        # Fetch historical bedtimes for consistency scoring.
        history_start = day_start - timedelta(days=sleep_config.rolling_window_nights + 1)
        hist_records, _ = self.event_record_repo.get_records_with_filters(
            db_session,
            EventRecordQueryParams(
                category="sleep",
                start_datetime=history_start,
                end_datetime=day_start,
                sort_by="start_datetime",
                sort_order="desc",
                limit=sleep_config.rolling_window_nights + 5,
            ),
            str(user_id),
        )

        historical_bedtimes = [
            r.start_datetime for r, _ in hist_records if isinstance(r.detail, SleepDetails) and not r.detail.is_nap
        ][: sleep_config.rolling_window_nights]

        sleep_stages: list[dict[str, str]] | None = None
        if detail.sleep_stages:
            sleep_stages = [
                {
                    "stage": s["stage"],
                    "start_time": s["start_time"],
                    "end_time": s["end_time"],
                }
                for s in detail.sleep_stages
            ]

        return self.get_sleep_score(
            total_sleep_duration_minutes=float(detail.sleep_total_duration_minutes or 0),
            deep_minutes=float(detail.sleep_deep_minutes or 0),
            rem_minutes=float(detail.sleep_rem_minutes or 0),
            awake_minutes=float(detail.sleep_awake_minutes or 0),
            session_start=record.start_datetime,
            historical_bedtimes=historical_bedtimes,
            sleep_stages=sleep_stages,
        )


sleep_score_service = SleepScoreService(log=getLogger(__name__))

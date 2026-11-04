"""Whether a sleep session's provider sent data after it: the evidence the session is over when the provider says
nothing about it."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import text

from app.database import DbSession
from app.schemas.enums import SeriesType, get_series_type_id

# Any of the user's sources at the session's provider counts: Polar files a night under the watch's device id and
# its heart rate and steps under a source without one. Per source, one index probe for a sample of steps, heart rate
# or MET from `since` on and one for a later day's steps row (a provider that sends daily totals only).
_WITH_DATA_SINCE = text("""
    SELECT d.record_id
    FROM unnest(CAST(:record_ids AS uuid[]), CAST(:source_ids AS uuid[]), CAST(:since AS timestamptz[]))
        AS d(record_id, source_id, since)
    JOIN data_source ds ON ds.id = d.source_id
    WHERE EXISTS (
        SELECT FROM data_source o
        WHERE o.user_id = ds.user_id AND o.provider = ds.provider AND (
            EXISTS (
                SELECT FROM series_sample s
                WHERE s.data_source_id = o.id AND s.series_type_definition_id = ANY(CAST(:type_ids AS int[]))
                    AND s.recorded_at >= d.since
            ) OR EXISTS (
                SELECT FROM series_aggregate a
                WHERE a.data_source_id = o.id AND a.series_type_definition_id = :steps_type_id
                    AND a.period_kind = 'day' AND a.period_start >= d.since
            )
        )
    )
""")
_TYPE_IDS = [get_series_type_id(t) for t in (SeriesType.steps, SeriesType.heart_rate, SeriesType.physical_effort)]
_STEPS_TYPE_ID = get_series_type_id(SeriesType.steps)


class SleepFinalityRepository:
    def with_data_since(self, db_session: DbSession, sessions: list[tuple[UUID, UUID, datetime]]) -> set[UUID]:
        """The record ids of the (record id, data source id, since) sessions whose provider sent data from `since`
        on."""
        if not sessions:
            return set()
        params = {
            "record_ids": [record_id for record_id, _, _ in sessions],
            "source_ids": [source_id for _, source_id, _ in sessions],
            "since": [since for _, _, since in sessions],
            "type_ids": _TYPE_IDS,
            "steps_type_id": _STEPS_TYPE_ID,
        }
        return set(db_session.execute(_WITH_DATA_SINCE, params).scalars())


sleep_finality_repository = SleepFinalityRepository()

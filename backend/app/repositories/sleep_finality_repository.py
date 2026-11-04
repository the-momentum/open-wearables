"""Whether a sleep session's source sent data after it: the evidence the session is over when the provider says
nothing about it."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import text

from app.database import DbSession
from app.schemas.enums import SeriesType, get_series_type_id

# Per session, one index probe on (data_source_id, series_type_definition_id, recorded_at) and one on the steps day
# rows: a sample of steps, heart rate or MET from `since` on, or a later day's steps row (a provider that sends daily
# totals only).
_WITH_DATA_SINCE = text("""
    SELECT d.record_id
    FROM unnest(CAST(:record_ids AS uuid[]), CAST(:source_ids AS uuid[]), CAST(:since AS timestamptz[]))
        AS d(record_id, source_id, since)
    WHERE EXISTS (
        SELECT FROM series_sample s
        WHERE s.data_source_id = d.source_id AND s.series_type_definition_id = ANY(CAST(:type_ids AS int[]))
            AND s.recorded_at >= d.since
    ) OR EXISTS (
        SELECT FROM series_aggregate a
        WHERE a.data_source_id = d.source_id AND a.series_type_definition_id = :steps_type_id
            AND a.period_kind = 'day' AND a.period_start >= d.since
    )
""")
_TYPE_IDS = [get_series_type_id(t) for t in (SeriesType.steps, SeriesType.heart_rate, SeriesType.physical_effort)]


class SleepFinalityRepository:
    def with_data_since(self, db_session: DbSession, sessions: list[tuple[UUID, UUID, datetime]]) -> set[UUID]:
        """The record ids of the (record id, data source id, since) sessions whose source sent data from `since` on."""
        if not sessions:
            return set()
        params = {
            "record_ids": [record_id for record_id, _, _ in sessions],
            "source_ids": [source_id for _, source_id, _ in sessions],
            "since": [since for _, _, since in sessions],
            "type_ids": _TYPE_IDS,
            "steps_type_id": get_series_type_id(SeriesType.steps),
        }
        return set(db_session.execute(_WITH_DATA_SINCE, params).scalars())


sleep_finality_repository = SleepFinalityRepository()

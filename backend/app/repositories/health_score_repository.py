from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from typing import cast as typing_cast
from uuid import UUID

from sqlalchemy import Date, and_, cast, delete, func, literal_column, or_, select, tuple_
from sqlalchemy.dialects.postgresql import insert

from app.database import DbSession
from app.models import DataSource, EventRecord, HealthScore, SleepDetails
from app.repositories.data_point_series_repository import WriteCounts
from app.repositories.local_day import OFFSET_REACH, utc_midnight
from app.repositories.repositories import CrudRepository, SourceRanking
from app.schemas.enums import EventCategory, HealthScoreCategory, ProviderName
from app.schemas.model_crud.activities import HealthScoreCreate, HealthScoreQueryParams, HealthScoreUpdate
from app.utils.dates import as_utc, local_date


def _utc_midnight(moment: datetime) -> datetime:
    """Start of the UTC day ``moment`` falls on; a naive moment is read as UTC."""
    return datetime.combine(as_utc(moment).date(), time.min, tzinfo=timezone.utc)


class HealthScoreRepository(CrudRepository[HealthScore, HealthScoreCreate, HealthScoreUpdate]):
    def get_by_all_components(self, db_session: DbSession, components: list[str]) -> list[HealthScore]:
        """Return health scores whose components JSONB contains all specified keys (?& operator)."""
        return db_session.query(HealthScore).filter(HealthScore.components.has_all(components)).all()

    def get_by_any_component(self, db_session: DbSession, components: list[str]) -> list[HealthScore]:
        """Return health scores whose components JSONB contains any of the specified keys (?| operator)."""
        return db_session.query(HealthScore).filter(HealthScore.components.has_any(components)).all()

    def get_with_filters(
        self,
        db_session: DbSession,
        user_id: UUID,
        params: HealthScoreQueryParams,
        ranking: SourceRanking,
    ) -> tuple[list[tuple[HealthScore, DataSource | None]], int]:
        """Scores newest first, with their data source; one OW score per category and day, picked before paging."""
        filters = [HealthScore.user_id == user_id]

        if params.category:
            filters.append(HealthScore.category == params.category)
        if params.provider:
            filters.append(HealthScore.provider == params.provider)
        if params.data_source_id:
            filters.append(HealthScore.data_source_id == params.data_source_id)
        # The pick sees whole days, so a bound inside a day can't hand the day to a lower-priority source
        rank_filters = list(filters)
        if params.start_datetime:
            filters.append(HealthScore.recorded_at >= params.start_datetime)
            rank_filters.append(HealthScore.recorded_at >= _utc_midnight(params.start_datetime))
        if params.end_datetime:
            filters.append(HealthScore.recorded_at < params.end_datetime)
            rank_filters.append(
                HealthScore.recorded_at
                < _utc_midnight(params.end_datetime - timedelta(microseconds=1)) + timedelta(days=1)
            )

        # Ranked by source: an OW score's own provider is always internal
        ranked = (
            select(
                HealthScore.id,
                func.row_number()
                .over(
                    # UTC date: a bare cast follows the session time zone
                    partition_by=(HealthScore.category, cast(func.timezone("UTC", HealthScore.recorded_at), Date)),
                    order_by=(
                        DataSource.id.is_(None),  # a score without a source comes last
                        *ranking.order_terms(),
                        # Longest sleep first, so an unflagged nap (#938) doesn't beat the night
                        func.coalesce(SleepDetails.sleep_total_duration_minutes, 0).desc(),
                        HealthScore.recorded_at.desc(),
                        HealthScore.id,
                    ),
                )
                .label("source_rank"),
            )
            .outerjoin(DataSource, HealthScore.data_source_id == DataSource.id)
            .outerjoin(SleepDetails, SleepDetails.record_id == HealthScore.event_record_id)
            .where(*rank_filters, HealthScore.provider == ProviderName.INTERNAL)
            .subquery()
        )
        filters.append(
            or_(
                HealthScore.provider != ProviderName.INTERNAL,
                HealthScore.id.in_(select(ranked.c.id).where(ranked.c.source_rank == 1)),
            )
        )

        query = (
            db_session.query(HealthScore, DataSource)
            .outerjoin(DataSource, HealthScore.data_source_id == DataSource.id)
            .filter(and_(*filters))
        )
        total_count = query.count()
        rows = (
            query.order_by(HealthScore.recorded_at.desc(), HealthScore.id.desc())
            .offset(params.offset)
            .limit(params.limit)
            .all()
        )
        return [(score, data_source) for score, data_source in rows], total_count

    def bulk_create(self, db_session: DbSession, creators: list[HealthScoreCreate]) -> WriteCounts:
        """Bulk insert health scores, doing nothing on conflict with the unique constraint.

        Returns the rows actually written. DO NOTHING never refreshes an existing
        row, so the count is all inserts — RETURNING yields a row only for the
        ones that were not conflicts.
        """
        if not creators:
            return WriteCounts(0, 0)

        creators = self._replace_earlier_scores_of_the_nights(db_session, creators)
        values = [c.model_dump() for c in creators]

        stmt = insert(HealthScore).values(values).on_conflict_do_nothing().returning(HealthScore.id)
        inserted = len(db_session.execute(stmt).scalars().all())
        # Caller is responsible for commit — allows batching with other operations
        return WriteCounts(inserted, 0)

    @staticmethod
    def _replace_earlier_scores_of_the_nights(
        db_session: DbSession, creators: list[HealthScoreCreate]
    ) -> list[HealthScoreCreate]:
        """A provider sleep score sits at its night's end, which a re-sent night moves (Whoop extends a scored
        night, Garmin a fragment): the night's earlier scores, from its start to its end, give way to the new one,
        stored or in the same batch.

        The night is the provider's sleep record ending at the score, stored before its score. A score linked to
        its record (Polar) is unique per record already.
        """
        ends = {
            (c.user_id, c.provider, c.recorded_at)
            for c in creators
            if c.category == HealthScoreCategory.SLEEP
            and c.provider != ProviderName.INTERNAL
            and c.event_record_id is None
        }
        if not ends:
            return creators
        night = (
            select(EventRecord.start_datetime, EventRecord.end_datetime, DataSource.user_id, DataSource.provider)
            .join(DataSource, DataSource.id == EventRecord.data_source_id)
            .where(
                EventRecord.category == EventCategory.SLEEP,
                tuple_(DataSource.user_id, DataSource.provider, EventRecord.end_datetime).in_(list(ends)),
            )
            .subquery()
        )
        nights = db_session.execute(select(night)).all()
        if not nights:
            return creators
        db_session.execute(
            delete(HealthScore)
            .where(
                HealthScore.category == HealthScoreCategory.SLEEP,
                HealthScore.event_record_id.is_(None),
                HealthScore.user_id == night.c.user_id,
                HealthScore.provider == night.c.provider,
                HealthScore.recorded_at >= night.c.start_datetime,
                HealthScore.recorded_at <= night.c.end_datetime,
            )
            .execution_options(synchronize_session=False)
        )
        return [
            c
            for c in creators
            if c.event_record_id is not None
            or not any(
                c.category == HealthScoreCategory.SLEEP
                and (c.user_id, c.provider) == (n.user_id, n.provider)
                and n.start_datetime <= c.recorded_at < n.end_datetime
                for n in nights
            )
        ]

    def drop_provider_sleep_score(self, db_session: DbSession, data_source_id: UUID, night_end: datetime) -> None:
        """The provider score at a night's former end, left behind when the provider moved that end."""
        db_session.execute(
            delete(HealthScore)
            .where(
                HealthScore.category == HealthScoreCategory.SLEEP,
                HealthScore.event_record_id.is_(None),
                HealthScore.provider != ProviderName.INTERNAL,
                tuple_(HealthScore.user_id, HealthScore.provider).in_(
                    select(DataSource.user_id, DataSource.provider).where(DataSource.id == data_source_id)
                ),
                HealthScore.recorded_at == night_end,
            )
            .execution_options(synchronize_session=False)
        )

    def bulk_create_keeping_highest(self, db_session: DbSession, creators: list[HealthScoreCreate]) -> WriteCounts:
        """Bulk upsert health scores, keeping the higher value when a score for the same time is sent again.

        For a peak the provider resends with more data as the day goes on, e.g. Garmin body battery.
        Scores without a value are skipped.
        """
        # The highest of each key: ON CONFLICT DO UPDATE can't touch a row twice in one statement
        with_value = sorted((c for c in creators if c.value is not None), key=lambda c: c.value or 0)
        highest = {(c.user_id, c.provider, c.data_source_id, c.category, c.recorded_at): c for c in with_value}
        if not highest:
            return WriteCounts(0, 0)

        stmt = insert(HealthScore).values([c.model_dump() for c in highest.values()])
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "provider", "data_source_id", "category", "recorded_at"],
            set_={"value": stmt.excluded.value},
            where=or_(HealthScore.value.is_(None), stmt.excluded.value > HealthScore.value),
        ).returning(literal_column("xmax = 0"))
        was_insert = db_session.execute(stmt).scalars().all()
        inserted = sum(was_insert)
        # Caller is responsible for commit — allows batching with other operations
        return WriteCounts(inserted, len(was_insert) - inserted)

    def get_latest_by_category(
        self,
        db_session: DbSession,
        user_id: UUID,
        category: HealthScoreCategory,
    ) -> HealthScore | None:
        """Return the most recent health score for a given category and user."""
        return (
            db_session.query(HealthScore)
            .filter(HealthScore.user_id == user_id, HealthScore.category == category)
            .order_by(HealthScore.recorded_at.desc())
            .first()
        )

    def delete_for_user_date(
        self,
        db_session: DbSession,
        user_id: UUID,
        score_date: date,
        category: HealthScoreCategory,
        provider: str = "internal",
    ) -> int:
        """Delete health scores matching user/category/provider/date without loading objects.

        Caller is responsible for commit. Returns deleted row count.
        Matches the whole day rather than an exact timestamp: sleep scores are anchored to
        the session's local wake time, and older rows sit at midnight of the same date.
        """
        day_start = datetime(score_date.year, score_date.month, score_date.day, tzinfo=timezone.utc)
        return (
            db_session.query(HealthScore)
            .filter(
                HealthScore.user_id == user_id,
                HealthScore.provider == provider,
                HealthScore.category == category,
                HealthScore.recorded_at >= day_start,
                HealthScore.recorded_at < day_start + timedelta(days=1),
            )
            .delete(synchronize_session=False)
        )

    def get_recovery_scores(
        self, db_session: DbSession, user_id: UUID, first_day: date, last_day: date
    ) -> list[dict[str, Any]]:
        """Recovery scores of the local days from ``first_day`` to ``last_day``, earliest first, keyed by their
        device's data source, else by the scoring provider; with the metrics a provider sent in the components."""
        rows = (
            db_session.query(HealthScore, DataSource)
            .outerjoin(DataSource, HealthScore.data_source_id == DataSource.id)
            .filter(
                HealthScore.user_id == user_id,
                HealthScore.category == HealthScoreCategory.RECOVERY,
                HealthScore.recorded_at >= utc_midnight(first_day) - OFFSET_REACH,
                HealthScore.recorded_at < utc_midnight(last_day) + timedelta(days=1) + OFFSET_REACH,
            )
            .order_by(HealthScore.recorded_at, HealthScore.id)
            .all()
        )

        return [
            {
                "recovery_date": local_date(row.recorded_at, row.zone_offset),
                "provider": data_source.provider if data_source else row.provider,
                "source": data_source.source if data_source else None,
                "device_model": data_source.device_model if data_source else None,
                "device_type": data_source.device_type if data_source else None,
                "recovery_score": int(row.value) if row.value is not None else None,
                "resting_heart_rate": typing_cast(dict, row.components or {})
                .get("resting_heart_rate", {})
                .get("value"),
                "hrv_rmssd_milli": typing_cast(dict, row.components or {}).get("hrv_rmssd_milli", {}).get("value"),
                "spo2_percentage": typing_cast(dict, row.components or {}).get("spo2_percentage", {}).get("value"),
            }
            for row, data_source in rows
            if first_day <= local_date(row.recorded_at, row.zone_offset) <= last_day
        ]

    def get_latest_per_category(
        self,
        db_session: DbSession,
        user_id: UUID,
    ) -> list[HealthScore]:
        """Return the most recent score for each category for a given user.

        Uses PostgreSQL DISTINCT ON (category) for efficiency.
        """
        return (
            db_session.query(HealthScore)
            .filter(HealthScore.user_id == user_id)
            .distinct(HealthScore.category)
            .order_by(HealthScore.category, HealthScore.recorded_at.desc())
            .all()
        )

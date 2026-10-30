from datetime import date, datetime, timedelta, timezone
from typing import Any
from typing import cast as typing_cast
from uuid import UUID

from sqlalchemy import Date, and_, cast, func, or_, select, tuple_
from sqlalchemy.dialects.postgresql import insert

from app.database import DbSession
from app.models import DataSource, HealthScore, SleepDetails
from app.repositories.data_point_series_repository import WriteCounts
from app.repositories.repositories import CrudRepository, source_priority_order
from app.schemas.enums import DeviceType, HealthScoreCategory, ProviderName
from app.schemas.model_crud.activities import HealthScoreCreate, HealthScoreQueryParams, HealthScoreUpdate
from app.utils.pagination import decode_cursor


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
        provider_order: dict[ProviderName, int],
        device_type_order: dict[DeviceType, int],
    ) -> tuple[list[tuple[HealthScore, DataSource | None]], int]:
        """Scores newest first, with their data source; one OW score per category and day, picked before paging."""
        filters = [HealthScore.user_id == user_id]

        if params.category:
            filters.append(HealthScore.category == params.category)
        if params.provider:
            filters.append(HealthScore.provider == params.provider)
        if params.data_source_id:
            filters.append(HealthScore.data_source_id == params.data_source_id)
        if params.start_datetime:
            filters.append(HealthScore.recorded_at >= params.start_datetime)
        if params.end_datetime:
            filters.append(HealthScore.recorded_at < params.end_datetime)

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
                        *source_priority_order(provider_order, device_type_order),
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
            .where(*filters, HealthScore.provider == ProviderName.INTERNAL)
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

        values = [c.model_dump() for c in creators]

        stmt = insert(HealthScore).values(values).on_conflict_do_nothing().returning(HealthScore.id)
        inserted = len(db_session.execute(stmt).scalars().all())
        # Caller is responsible for commit — allows batching with other operations
        return WriteCounts(inserted, 0)

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

    def get_recovery_summaries(
        self,
        db_session: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
        cursor: str | None,
        limit: int,
        provider_order: dict[ProviderName, int],
        device_type_order: dict[DeviceType, int],
    ) -> list[dict[str, Any]]:
        """Get recovery health scores for a date range with cursor-based pagination.

        Per date only the highest-priority source's earliest score is kept, picked before pagination
        so a page holds `limit` dates however many sources scored each day.

        Returns list of dicts with keys: recovery_date, provider, source, device_model,
        device_type, record_id, recorded_at, recovery_score, resting_heart_rate,
        hrv_rmssd_milli, spo2_percentage.
        Fetches limit+1 rows so callers can detect has_more without a separate COUNT query.
        Ordering matches get_sleep_summaries: ASC by default, DESC when paginating backward.
        """
        # Provider scores have no data_source, so the provider rank comes from the score itself
        ranked = (
            select(
                HealthScore.id,
                func.row_number()
                .over(
                    partition_by=cast(HealthScore.recorded_at, Date),
                    order_by=(
                        *source_priority_order(provider_order, device_type_order, HealthScore.provider),
                        HealthScore.recorded_at,
                        HealthScore.id,
                    ),
                )
                .label("source_rank"),
            )
            .outerjoin(DataSource, HealthScore.data_source_id == DataSource.id)
            .where(
                HealthScore.user_id == user_id,
                HealthScore.category == HealthScoreCategory.RECOVERY,
                HealthScore.recorded_at >= start_date,
                HealthScore.recorded_at < end_date,
            )
            .subquery()
        )
        # Outer join so scores without a data_source (older rows) still come back.
        query = (
            db_session.query(HealthScore, DataSource)
            .outerjoin(DataSource, HealthScore.data_source_id == DataSource.id)
            .filter(HealthScore.id.in_(select(ranked.c.id).where(ranked.c.source_rank == 1)))
        )

        if cursor:
            cursor_ts, cursor_id, direction = decode_cursor(cursor)
            if direction == "prev":
                query = query.filter(tuple_(HealthScore.recorded_at, HealthScore.id) < (cursor_ts, cursor_id)).order_by(
                    HealthScore.recorded_at.desc(), HealthScore.id.desc()
                )
            else:
                query = query.filter(tuple_(HealthScore.recorded_at, HealthScore.id) > (cursor_ts, cursor_id)).order_by(
                    HealthScore.recorded_at.asc(), HealthScore.id.asc()
                )
        else:
            query = query.order_by(HealthScore.recorded_at.asc(), HealthScore.id.asc())

        rows = query.limit(limit + 1).all()

        return [
            {
                "recovery_date": row.recorded_at.date(),
                "provider": row.provider,
                "source": data_source.source if data_source else None,
                "device_model": data_source.device_model if data_source else None,
                "device_type": data_source.device_type if data_source else None,
                "record_id": row.id,
                "recorded_at": row.recorded_at,
                "recovery_score": int(row.value) if row.value is not None else None,
                "resting_heart_rate": typing_cast(dict, row.components or {})
                .get("resting_heart_rate", {})
                .get("value"),
                "hrv_rmssd_milli": typing_cast(dict, row.components or {}).get("hrv_rmssd_milli", {}).get("value"),
                "spo2_percentage": typing_cast(dict, row.components or {}).get("spo2_percentage", {}).get("value"),
            }
            for row, data_source in rows
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

from datetime import date
from logging import Logger
from typing import TypeVar
from uuid import UUID

from sqlalchemy import desc

from app.database import BaseDbModel, DbSession
from app.models import ExternalDeviceMapping
from app.models.summaries import (
    DailyActivitySummary,
    DailyBodySummary,
    DailyRecoverySummary,
)
from app.repositories.repositories import CrudRepository
from app.repositories.summaries_repository import (
    DailyActivitySummaryRepository,
    DailyBodySummaryRepository,
    DailyRecoverySummaryRepository,
)
from app.schemas.taxonomy_common import DataSource, Pagination
from app.schemas.taxonomy_summaries import (
    ActivitySummary,
    BodySummary,
    RecoverySummary,
)

T = TypeVar("T", bound=BaseDbModel)
S = TypeVar("S")


class SummariesService:
    def __init__(self, log: Logger):
        self.log = log
        self.activity_repo = DailyActivitySummaryRepository()
        self.body_repo = DailyBodySummaryRepository()
        self.recovery_repo = DailyRecoverySummaryRepository()

    def _get_summaries(
        self,
        db: DbSession,
        repo: CrudRepository,
        model_cls: type[T],
        schema_cls: type[S],
        user_id: UUID,
        start_date: date,
        end_date: date,
        limit: int,
        cursor: str | None,
    ) -> dict[str, list[S] | Pagination]:
        query = (
            db.query(model_cls, ExternalDeviceMapping)
            .join(
                ExternalDeviceMapping,
                model_cls.external_mapping_id == ExternalDeviceMapping.id,
            )
            .filter(
                ExternalDeviceMapping.user_id == user_id,
                model_cls.date >= start_date,
                model_cls.date <= end_date,
            )
        )

        if cursor:
            # Assuming cursor is a date string for simplicity in this draft
            query = query.filter(model_cls.date < cursor)

        query = query.order_by(desc(model_cls.date))
        results = query.limit(limit + 1).all()

        has_more = len(results) > limit
        data = results[:limit]

        next_cursor = None
        if has_more and data:
            next_cursor = data[-1][0].date.isoformat()

        items = []
        for row in data:
            summary: T = row[0]
            mapping: ExternalDeviceMapping = row[1]

            # Convert SQLAlchemy model to Pydantic schema
            # We need to handle the 'source' field manually
            summary_dict = {c.name: getattr(summary, c.name) for c in summary.__table__.columns}

            # Handle nested JSONB fields mapping to Pydantic models
            if "intensity_minutes" in summary_dict and summary_dict["intensity_minutes"]:
                # Assuming the JSON structure matches the Pydantic model
                pass
            if "blood_pressure" in summary_dict and summary_dict["blood_pressure"]:
                pass

            summary_dict["source"] = DataSource(
                provider=mapping.provider_id,
                device=mapping.device_id or "Unknown",
            )
            items.append(schema_cls(**summary_dict))

        return {
            "data": items,
            "pagination": Pagination(
                has_more=has_more,
                next_cursor=next_cursor,
                previous_cursor=None,  # Not implemented for now
            ),
        }

    def get_activity_summaries(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: date,
        end_date: date,
        limit: int,
        cursor: str | None,
    ) -> dict[str, list[ActivitySummary] | Pagination]:
        return self._get_summaries(
            db,
            self.activity_repo,
            DailyActivitySummary,
            ActivitySummary,
            user_id,
            start_date,
            end_date,
            limit,
            cursor,
        )

    def get_body_summaries(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: date,
        end_date: date,
        limit: int,
        cursor: str | None,
    ) -> dict[str, list[BodySummary] | Pagination]:
        return self._get_summaries(
            db,
            self.body_repo,
            DailyBodySummary,
            BodySummary,
            user_id,
            start_date,
            end_date,
            limit,
            cursor,
        )

    def get_recovery_summaries(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: date,
        end_date: date,
        limit: int,
        cursor: str | None,
    ) -> dict[str, list[RecoverySummary] | Pagination]:
        return self._get_summaries(
            db,
            self.recovery_repo,
            DailyRecoverySummary,
            RecoverySummary,
            user_id,
            start_date,
            end_date,
            limit,
            cursor,
        )


summaries_service = SummariesService(Logger("summaries_service"))

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, desc
from sqlalchemy.orm import Query

from app.database import DbSession
from app.models import Record
from app.repositories import CrudRepository
from app.schemas import HKRecordQueryParams, HKRecordCreate, HKRecordUpdate


class RecordRepository(CrudRepository[Record, HKRecordCreate, HKRecordUpdate]):
    def __init__(self, model: type[Record]):
        super().__init__(model)

    def get_records_with_filters(
        self,
        db_session: DbSession,
        query_params: HKRecordQueryParams,
        user_id: str
    ) -> tuple[list[Record], int]:
        query: Query = db_session.query(Record)

        # Apply filters
        filters = []

        # User ID filter (always required for security)
        filters.append(Record.user_id == user_id)

        # Date range filters
        if query_params.start_date:
            start_dt = datetime.fromisoformat(
                query_params.start_date.replace("Z", "+00:00")
            )
            filters.append(Record.startDate >= start_dt)

        if query_params.end_date:
            end_dt = datetime.fromisoformat(query_params.end_date.replace("Z", "+00:00"))
            filters.append(Record.endDate <= end_dt)

        # Record type filter
        if query_params.record_type:
            filters.append(Record.type.ilike(f"%{query_params.record_type}%"))

        # Source name filter
        if query_params.source_name:
            filters.append(Record.sourceName.ilike(f"%{query_params.source_name}%"))

        # Unit filter
        if query_params.unit:
            filters.append(Record.unit == query_params.unit)

        # Value filters
        if query_params.min_value is not None:
            filters.append(Record.value >= Decimal(query_params.min_value))

        if query_params.max_value is not None:
            filters.append(Record.value <= Decimal(query_params.max_value))

        # Apply all filters
        if filters:
            query = query.filter(and_(*filters))

        # Get total count before pagination
        total_count = query.count()

        # Apply sorting
        sort_column = getattr(Record, query_params.sort_by, Record.startDate)
        if query_params.sort_order == "asc":
            query = query.order_by(sort_column)
        else:
            query = query.order_by(desc(sort_column))

        # Apply pagination
        query = query.offset(query_params.offset).limit(query_params.limit)

        return query.all(), total_count

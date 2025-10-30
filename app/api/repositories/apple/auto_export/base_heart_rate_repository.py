from datetime import datetime
from decimal import Decimal

from sqlalchemy import and_, desc
from sqlalchemy.orm import Query

from app.database import BaseDbModel, DbSession
from app.schemas import AEHeartRateQueryParams


class BaseHeartRateRepository[HeartRateModel: BaseDbModel]:
    def __init__(self, model: type[HeartRateModel]):
        self.model = model

    def _apply_common_filters(
        self, 
        query: Query, 
        query_params: AEHeartRateQueryParams, 
        user_id: str
    ) -> Query:
        filters = []
        
        # User ID filter (always required)
        filters.append(self.model.user_id == user_id)

        # Date range filters
        if query_params.start_date:
            start_dt = datetime.fromisoformat(
                query_params.start_date.replace("Z", "+00:00")
            )
            filters.append(self.model.date >= start_dt)

        if query_params.end_date:
            end_dt = datetime.fromisoformat(query_params.end_date.replace("Z", "+00:00"))
            filters.append(self.model.date <= end_dt)

        # Workout ID filter
        if query_params.workout_id:
            filters.append(self.model.workout_id == query_params.workout_id)

        # Source filter
        if query_params.source:
            filters.append(self.model.source.ilike(f"%{query_params.source}%"))

        # Heart rate value filters
        if query_params.min_avg is not None:
            filters.append(self.model.avg >= Decimal(str(query_params.min_avg)))

        if query_params.max_avg is not None:
            filters.append(self.model.avg <= Decimal(str(query_params.max_avg)))

        if query_params.min_max is not None:
            filters.append(self.model.max >= Decimal(str(query_params.min_max)))

        if query_params.max_max is not None:
            filters.append(self.model.max <= Decimal(str(query_params.max_max)))

        if query_params.min_min is not None:
            filters.append(self.model.min >= Decimal(str(query_params.min_min)))

        if query_params.max_min is not None:
            filters.append(self.model.min <= Decimal(str(query_params.max_min)))

        # Apply all filters
        if filters:
            query = query.filter(and_(*filters))

        return query

    def _apply_sorting_and_pagination(
        self, 
        query: Query, 
        query_params: AEHeartRateQueryParams
    ) -> Query:
        """
        Apply sorting and pagination to query.
        
        Args:
            query: SQLAlchemy query object
            query_params: Query parameters for sorting and pagination
            
        Returns:
            Query with sorting and pagination applied
        """
        # Apply sorting
        sort_column = getattr(self.model, query_params.sort_by, self.model.date)
        if query_params.sort_order == "asc":
            query = query.order_by(sort_column)
        else:
            query = query.order_by(desc(sort_column))

        # Apply pagination
        query = query.offset(query_params.offset).limit(query_params.limit)

        return query

    def get_heart_rate_with_filters(
        self, 
        db_session: DbSession, 
        query_params: AEHeartRateQueryParams,
        user_id: str
    ) -> tuple[list[HeartRateModel], int]:
        query: Query = db_session.query(self.model)

        # Apply common filters
        query = self._apply_common_filters(query, query_params, user_id)

        # Get total count before pagination
        total_count = query.count()

        # Apply sorting and pagination
        query = self._apply_sorting_and_pagination(query, query_params)

        return query.all(), total_count

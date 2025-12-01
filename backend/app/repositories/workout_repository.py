from decimal import Decimal
from uuid import UUID

import isodate
from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Query

from app.database import DbSession
from app.models import Workout, WorkoutStatistic
from app.repositories.repositories import CrudRepository
from app.schemas import WorkoutCreate, WorkoutQueryParams, WorkoutUpdate


class WorkoutRepository(CrudRepository[Workout, WorkoutCreate, WorkoutUpdate]):
    def __init__(self, model: type[Workout]):
        super().__init__(model)

    def get_workouts_with_filters(
        self,
        db_session: DbSession,
        query_params: WorkoutQueryParams,
        user_id: str,
    ) -> tuple[list[Workout], int]:
        query: Query = db_session.query(Workout)

        # Apply filters
        filters = []

        # User ID filter (always required for security)
        filters.append(Workout.user_id == UUID(user_id))

        # Date range filters
        if query_params.start_date:
            start_dt = isodate.parse_datetime(query_params.start_date)
            filters.append(Workout.start_datetime >= start_dt)

        if query_params.end_date:
            end_dt = isodate.parse_datetime(query_params.end_date)
            filters.append(Workout.end_datetime <= end_dt)

        # Workout type filter
        if query_params.workout_type:
            filters.append(Workout.type.ilike(f"%{query_params.workout_type}%"))

        # Source name filter
        if query_params.source_name:
            filters.append(Workout.source_name.ilike(f"%{query_params.source_name}%"))

        # Duration filters
        if query_params.min_duration is not None:
            filters.append(Workout.duration_seconds >= Decimal(query_params.min_duration))

        if query_params.max_duration is not None:
            filters.append(Workout.duration_seconds <= Decimal(query_params.max_duration))


        # Apply all filters
        if filters:
            query = query.filter(and_(*filters))

        # Get total count before pagination
        total_count = query.count()

        # Apply sorting
        sort_column = getattr(Workout, query_params.sort_by, Workout.start_datetime)  # type: ignore[no-matching-overload]

        query = query.order_by(sort_column) if query_params.sort_order == "asc" else query.order_by(desc(sort_column))

        # Apply pagination
        query = query.offset(query_params.offset).limit(query_params.limit)

        return query.all(), total_count

    def get_workout_summary(self, db_session: DbSession, workout_id: UUID) -> dict:
        """Get workout summary statistics for HealthKit workouts."""

        # Get workout statistics summary
        stats_summary = (
            db_session.query(
                func.count(WorkoutStatistic.id).label("total_statistics"),
                func.avg(WorkoutStatistic.avg).label("avg_value"),
                func.max(WorkoutStatistic.max).label("max_value"),
                func.min(WorkoutStatistic.min).label("min_value"),
            )
            .filter(WorkoutStatistic.workout_id == workout_id)
            .first()
        )

        # Get heart rate summary
        hr_stats = (
            db_session.query(
                func.avg(WorkoutStatistic.avg).label("avg_hr"),
                func.max(WorkoutStatistic.max).label("max_hr"),
                func.min(WorkoutStatistic.min).label("min_hr"),
            )
            .filter(WorkoutStatistic.workout_id == workout_id)
            .filter(WorkoutStatistic.type == "heartRate")
            .first()
        )


        return {
            "total_statistics": int(stats_summary.total_statistics or 0),
            "avg_statistic_value": float(stats_summary.avg_value or 0),
            "max_statistic_value": float(stats_summary.max_value or 0),
            "min_statistic_value": float(stats_summary.min_value or 0),
            "avg_heart_rate": float(hr_stats.avg_hr or 0),
            "max_heart_rate": float(hr_stats.max_hr or 0),
            "min_heart_rate": float(hr_stats.min_hr or 0),
        }

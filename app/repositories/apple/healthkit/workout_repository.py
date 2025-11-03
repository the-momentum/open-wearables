from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, desc
from sqlalchemy.orm import Query

from app.database import DbSession
from app.models import Workout
from app.repositories import CrudRepository
from app.schemas import HKWorkoutQueryParams, HKWorkoutCreate, HKWorkoutUpdate


class WorkoutRepository(CrudRepository[Workout, HKWorkoutCreate, HKWorkoutUpdate]):
    def __init__(self, model: type[Workout]):
        super().__init__(model)

    def get_workouts_with_filters(
        self,
        db_session: DbSession,
        query_params: HKWorkoutQueryParams,
        user_id: str
    ) -> tuple[list[Workout], int]:
        query: Query = db_session.query(Workout)

        # Apply filters
        filters = []

        # User ID filter (always required for security)
        filters.append(Workout.user_id == user_id)

        # Date range filters
        if query_params.start_date:
            start_dt = datetime.fromisoformat(
                query_params.start_date.replace("Z", "+00:00")
            )
            filters.append(Workout.startDate >= start_dt)

        if query_params.end_date:
            end_dt = datetime.fromisoformat(query_params.end_date.replace("Z", "+00:00"))
            filters.append(Workout.endDate <= end_dt)

        # Workout type filter
        if query_params.workout_type:
            filters.append(Workout.type.ilike(f"%{query_params.workout_type}%"))

        # Source name filter
        if query_params.source_name:
            filters.append(Workout.sourceName.ilike(f"%{query_params.source_name}%"))

        # Duration filters
        if query_params.min_duration is not None:
            filters.append(Workout.duration >= Decimal(query_params.min_duration))

        if query_params.max_duration is not None:
            filters.append(Workout.duration <= Decimal(query_params.max_duration))

        # Duration unit filter
        if query_params.duration_unit:
            filters.append(Workout.durationUnit == query_params.duration_unit)

        # Apply all filters
        if filters:
            query = query.filter(and_(*filters))

        # Get total count before pagination
        total_count = query.count()

        # Apply sorting
        sort_column = getattr(Workout, query_params.sort_by, Workout.startDate)
        if query_params.sort_order == "asc":
            query = query.order_by(sort_column)
        else:
            query = query.order_by(desc(sort_column))

        # Apply pagination
        query = query.offset(query_params.offset).limit(query_params.limit)

        return query.all(), total_count

    def get_workout_summary(self, db_session: DbSession, workout_id: UUID) -> dict:
        """Get workout summary statistics for HealthKit workouts."""
        from app.models import WorkoutStatistic, HeartRateData, ActiveEnergy
        from sqlalchemy import func

        # Get workout statistics summary
        stats_summary = (
            db_session.query(
                func.count(WorkoutStatistic.id).label("total_statistics"),
                func.avg(WorkoutStatistic.value).label("avg_value"),
                func.max(WorkoutStatistic.value).label("max_value"),
                func.min(WorkoutStatistic.value).label("min_value"),
            )
            .filter(WorkoutStatistic.workout_id == workout_id)
            .first()
        )

        # Get heart rate summary
        hr_stats = (
            db_session.query(
                func.avg(HeartRateData.avg).label("avg_hr"),
                func.max(HeartRateData.max).label("max_hr"),
                func.min(HeartRateData.min).label("min_hr"),
            )
            .filter(HeartRateData.workout_id == workout_id)
            .first()
        )

        # Get total calories from active energy
        total_calories = (
            db_session.query(
                func.sum(ActiveEnergy.qty).label("total_calories"),
            )
            .filter(ActiveEnergy.workout_id == workout_id)
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
            "total_calories": float(total_calories.total_calories or 0),
        }

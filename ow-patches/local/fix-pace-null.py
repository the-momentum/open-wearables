# patch_id:        fix-pace-null
# upstream_file:   backend/app/services/event_record_service.py
# upstream_symbol: EventRecordService.get_workouts
# retire_when:     Workout list response (get_workouts → Workout.avg_pace_sec_per_km) returns a non-null int for running/walking/cycling workouts that have distance and duration. Marker: presence of `_compute_avg_pace_sec_per_km` in upstream.

"""Compute avg_pace_sec_per_km in the workout list response.

Upstream's list path hard-codes `avg_pace_sec_per_km=None` (the comment in the
source file literally reads `# Derived or in details?`). The detailed view does
compute pace, so the inconsistency is consumer-visible. This patch ports the
same derivation to the list view, behind a shared helper.
"""

from uuid import UUID

from app.database import DbSession
from app.models import WorkoutDetails
from app.schemas.enums import WORKOUTS_WITH_PACE
from app.schemas.model_crud.activities import EventRecordQueryParams
from app.schemas.responses.activity import Workout
from app.schemas.utils import (
    PaginatedResponse,
    Pagination,
    TimeseriesMetadata,
)
from app.utils.exceptions import handle_exceptions
from app.utils.pagination import encode_cursor


def compute_avg_pace_sec_per_km(
    workout_type: str | None,
    duration_seconds: int | None,
    details: WorkoutDetails | None,
) -> int | None:
    """Derive average pace (sec/km) for pace-meaningful workouts.

    Prefers explicit average_speed when present; otherwise derives from duration
    and distance. Returns None for workout types where pace is meaningless
    (strength, yoga, generic/other) or when inputs are missing.
    """
    if not details or workout_type not in WORKOUTS_WITH_PACE:
        return None
    avg_speed = float(details.average_speed) if details.average_speed is not None else None
    if avg_speed is not None and avg_speed > 0:
        return round(1000 / avg_speed)
    distance = float(details.distance) if details.distance is not None else None
    if duration_seconds is not None and distance is not None and distance > 0:
        return round(duration_seconds / (distance / 1000))
    return None


@handle_exceptions
def get_workouts(
    self,
    db_session: DbSession,
    user_id: UUID,
    params: EventRecordQueryParams,
) -> PaginatedResponse[Workout]:
    """List workouts with avg_pace_sec_per_km populated."""
    params.category = "workout"
    records, total_count = self._get_records_with_filters(db_session, params, str(user_id))
    total_count = total_count if total_count is not None else 0

    limit = params.limit or 20
    has_more = len(records) > limit

    is_backward = params.cursor and params.cursor.startswith("prev_")

    if has_more:
        records = records[-limit:] if is_backward else records[:limit]

    next_cursor = None
    previous_cursor = None

    if records:
        if has_more:
            last_record, _ = records[-1]
            next_cursor = encode_cursor(last_record.start_datetime, last_record.id, "next")

        if params.cursor:
            if is_backward:
                if has_more:
                    first_record, _ = records[0]
                    previous_cursor = encode_cursor(first_record.start_datetime, first_record.id, "prev")
            else:
                first_record, _ = records[0]
                previous_cursor = encode_cursor(first_record.start_datetime, first_record.id, "prev")

    computed_hr = self._resolve_avg_hr(db_session, [r for r, _ in records])

    data = []
    for record, data_source in records:
        # Upstream #1314 removed EventRecord.detail (polymorphic) in favour of a
        # dedicated workout_detail relationship — mirror upstream's own access.
        details: WorkoutDetails | None = record.workout_detail

        # Constructor mirrors upstream/main (#1510 added name / entry_source /
        # intensity from WorkoutDetails) with ONE fork difference: the
        # avg_pace_sec_per_km kwarg below. Re-diff on every reconcile.
        workout = Workout(
            id=record.id,
            type=record.type or "unknown",
            name=details.label if details else None,
            start_time=record.start_datetime,
            end_time=record.end_datetime,
            zone_offset=record.zone_offset,
            duration_seconds=record.duration_seconds,
            source=self._map_source(data_source),
            entry_source=details.entry_source if details else None,
            intensity=details.intensity if details else None,
            calories_kcal=float(details.energy_burned) if details and details.energy_burned else None,
            distance_meters=float(details.distance) if details and details.distance else None,
            avg_heart_rate_bpm=computed_hr.get(record.id),
            max_heart_rate_bpm=details.heart_rate_max if details else None,
            avg_pace_sec_per_km=compute_avg_pace_sec_per_km(record.type, record.duration_seconds, details),
            elevation_gain_meters=float(details.total_elevation_gain) if details and details.total_elevation_gain else None,
        )
        data.append(workout)

    return PaginatedResponse(
        data=data,
        pagination=Pagination(
            has_more=has_more,
            next_cursor=next_cursor,
            previous_cursor=previous_cursor,
            total_count=total_count,
        ),
        metadata=TimeseriesMetadata(
            sample_count=len(data),
            start_time=params.start_datetime,
            end_time=params.end_datetime,
        ),
    )


def install() -> None:
    """Replace EventRecordService.get_workouts and expose the helper."""
    from app.services.event_record_service import EventRecordService

    EventRecordService.get_workouts = get_workouts
    EventRecordService._compute_avg_pace_sec_per_km = staticmethod(compute_avg_pace_sec_per_km)

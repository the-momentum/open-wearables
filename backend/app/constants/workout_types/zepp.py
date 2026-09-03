import logging

from app.schemas.enums import WorkoutType
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)

ZEPP_ID_TO_WORKOUT_TYPE: dict[int, WorkoutType] = {
    1: WorkoutType.RUNNING,
    6: WorkoutType.WALKING,
    7: WorkoutType.HIKING,
    8: WorkoutType.TREADMILL,
    9: WorkoutType.CYCLING,
    10: WorkoutType.INDOOR_CYCLING,
    12: WorkoutType.SWIMMING,
    14: WorkoutType.POOL_SWIMMING,
    15: WorkoutType.OPEN_WATER_SWIMMING,
    16: WorkoutType.ELLIPTICAL,
    17: WorkoutType.ROWING_MACHINE,
    40: WorkoutType.OTHER,
    52: WorkoutType.STRENGTH_TRAINING,
    54: WorkoutType.STRETCHING,
    56: WorkoutType.YOGA,
    57: WorkoutType.PILATES,
    82: WorkoutType.CARDIO_TRAINING,
    83: WorkoutType.CARDIO_TRAINING,
}

TYPE_NAMES: dict[int, str] = {
    1: "Corrida",
    6: "Caminhada",
    7: "Trilha",
    8: "Esteira",
    9: "Ciclismo",
    10: "Ciclismo Indoor",
    12: "Natação",
    14: "Natação em Piscina",
    15: "Natação em Águas Abertas",
    16: "Elíptico",
    17: "Remo",
    40: "Outro",
    52: "Treino Força",
    54: "Alongamento",
    56: "Yoga",
    57: "Pilates",
    82: "HIIT",
    83: "Pular Corda",
}


def get_unified_workout_type(activity_type_id: int, activity_name: str | None = None) -> WorkoutType:
    """Map a Zepp / Huami activity type ID to the unified WorkoutType enum.

    Args:
        activity_type_id: The integer sport/activity type ID from the Zepp API.
        activity_name: Optional activity name string for fallback matching.

    Returns:
        WorkoutType: The corresponding unified WorkoutType, or WorkoutType.OTHER.
    """
    unified_type = ZEPP_ID_TO_WORKOUT_TYPE.get(activity_type_id)
    if unified_type is not None:
        return unified_type

    log_structured(
        logger,
        "warning",
        "Unmapped Zepp activity type, falling back to OTHER",
        provider="zepp",
        activity_type_id=activity_type_id,
        activity_name=activity_name,
    )
    return WorkoutType.OTHER

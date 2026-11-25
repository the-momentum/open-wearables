from collections.abc import Iterable

from app.constants.sleep import SleepStageType
from app.schemas.model_crud.activities.sleep import SleepStage


def measured_stages(stages: Iterable[SleepStage]) -> tuple[bool, bool]:
    """Whether a hypnogram measures the light/deep/rem phases, and whether it measures awake time.

    One of only ``sleeping`` or ``in_bed`` segments carries no phases, so their minutes are unknown.
    Awake time is measured once the hypnogram has phases or any ``awake`` segment.
    """
    kinds = {s.stage for s in stages}
    has_phases = not kinds.isdisjoint({SleepStageType.LIGHT, SleepStageType.DEEP, SleepStageType.REM})
    return has_phases, has_phases or SleepStageType.AWAKE in kinds

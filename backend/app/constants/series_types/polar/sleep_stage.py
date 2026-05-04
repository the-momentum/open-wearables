"""Polar Sleep Plus Stages hypnogram code → unified SleepStageType.

Polar's AccessLink v3 `sleep.hypnogram` is a mapping of ``"HH:MM"`` transition
times to stage codes. Codes are documented as::

    0 = WAKE
    1 = REM
    2 = LIGHTER NON-REM   (AASM N1)
    3 = LIGHT NON-REM     (AASM N2)
    4 = DEEP NON-REM      (AASM N3)
    5 = UNKNOWN           (e.g. poor skin contact)

OW's `SleepStageType` has a single ``LIGHT`` bucket, so 2 and 3 both map to it.
Codes outside this range fall back to ``UNKNOWN`` at the call site.
"""

from app.constants.sleep import SleepStageType

POLAR_HYPNOGRAM_MAP: dict[int, SleepStageType] = {
    0: SleepStageType.AWAKE,
    1: SleepStageType.REM,
    2: SleepStageType.LIGHT,
    3: SleepStageType.LIGHT,
    4: SleepStageType.DEEP,
    5: SleepStageType.UNKNOWN,
}

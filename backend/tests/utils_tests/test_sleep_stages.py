"""Tests for telling which sleep stages a hypnogram measures."""

from datetime import datetime, timedelta, timezone

import pytest

from app.constants.sleep import SleepStageType
from app.schemas.model_crud.activities.sleep import SleepStage
from app.utils.sleep_stages import measured_stages

_START = datetime(2025, 3, 10, 23, 0, tzinfo=timezone.utc)


def _hypnogram(*stages: SleepStageType) -> list[SleepStage]:
    return [
        SleepStage(
            stage=stage,
            start_time=_START + timedelta(minutes=30 * i),
            end_time=_START + timedelta(minutes=30 * (i + 1)),
        )
        for i, stage in enumerate(stages)
    ]


@pytest.mark.parametrize(
    ("stages", "expected"),
    [
        ((), (False, False)),
        ((SleepStageType.IN_BED,), (False, False)),
        ((SleepStageType.SLEEPING, SleepStageType.UNKNOWN), (False, False)),
        ((SleepStageType.SLEEPING, SleepStageType.AWAKE), (False, True)),
        ((SleepStageType.AWAKE,), (False, True)),
        ((SleepStageType.LIGHT, SleepStageType.DEEP), (True, True)),
        ((SleepStageType.SLEEPING, SleepStageType.REM), (True, True)),
    ],
)
def test_measured_stages(stages: tuple[SleepStageType, ...], expected: tuple[bool, bool]) -> None:
    assert measured_stages(_hypnogram(*stages)) == expected

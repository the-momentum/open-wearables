from datetime import datetime

from pydantic import BaseModel

from app.constants.sleep import SleepStageType


class SleepStage(BaseModel):
    """A single continuous sleep stage interval stored inside the JSONB column."""

    stage: SleepStageType
    start_time: datetime
    end_time: datetime

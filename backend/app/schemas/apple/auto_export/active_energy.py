from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class ActiveEnergyCreate(BaseModel):
    """Schema for creating active energy data."""
    
    user_id: UUID
    workout_id: UUID
    date: datetime
    source: str | None = None
    units: str | None = None
    qty: Decimal | None = None


class ActiveEnergyUpdate(BaseModel):
    """Schema for updating active energy data."""
    
    date: datetime | None = None
    source: str | None = None
    units: str | None = None
    qty: Decimal | None = None

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel
from sqlalchemy.inspection import inspect

from app.database import BaseDbModel


def to_decimal(value: Any) -> Decimal | None:
    """Coerce a numeric value (often a string) to Decimal; None if not numeric."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def as_int(value: Any) -> int | None:
    """Coerce a value to int; None if missing or not convertible (e.g. NaN/Infinity)."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError, OverflowError):
        return None


def as_float(value: Any) -> float | None:
    """Coerce a value to float; None if missing or not convertible.

    Zero is a real reading (0 W of power, 0 m of elevation), so only None maps to None.
    """
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError, OverflowError):
        return None


def as_model[ModelT: BaseModel](model: type[ModelT], value: Any) -> ModelT | None:
    """Validate a raw mapping into a Pydantic model; None if empty.

    json_binary columns hand back plain dicts, which Pydantic would otherwise carry
    through unvalidated.
    """
    return model.model_validate(value) if value else None


_KCAL_PER_KJ = Decimal("0.239006")  # 1 kcal = 4.184 kJ


def kilojoules_to_kcal(kilojoules: Any) -> Decimal | None:
    """Convert kilojoules to kilocalories; None if not numeric."""
    kj = to_decimal(kilojoules)
    return kj * _KCAL_PER_KJ if kj is not None else None


def base_to_dict(instance: BaseDbModel) -> dict[str, str | None]:
    """Function to convert SQLALchemy Base model into dict."""
    b2d = {}
    for column in inspect(instance).mapper.column_attrs:
        value = getattr(instance, column.key)

        if isinstance(value, (datetime)):
            value = value.isoformat()

        b2d[column.key] = value

    return b2d

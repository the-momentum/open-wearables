from datetime import datetime

from sqlalchemy.inspection import inspect

from app.database import BaseDbModel


def base_to_dict(instance: BaseDbModel) -> dict[str, str | None]:
    """Function to convert SQLALchemy Base model into dict."""
    b2d = {}
    for column in inspect(instance).mapper.column_attrs:
        value = getattr(instance, column.key)

        if isinstance(value, (datetime)):
            value = value.isoformat()

        b2d[column.key] = value

    return b2d

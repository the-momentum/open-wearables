from functools import wraps
from typing import Callable, TypeVar

from psycopg.errors import UniqueViolation
from sqlalchemy import UniqueConstraint
from sqlalchemy.exc import IntegrityError as SQLAIntegrityError
from sqlalchemy.inspection import inspect

T = TypeVar("T")


def handle_duplicates(func: Callable[..., T]) -> Callable[..., T | None]:
    """
    Decorator that handles duplicate inserts by querying for existing records
    based on unique constraints or primary keys.

    When a unique constraint violation occurs, this decorator tries each unique
    constraint sequentially until it finds the existing record that caused the violation.
    """

    @wraps(func)
    def wrapper(*args, **kwargs) -> T | None:
        try:
            return func(*args, **kwargs)
        except SQLAIntegrityError as e:
            if isinstance(e.orig, UniqueViolation):
                model = args[0].model
                db_session = args[1]
                creator = args[2]

                db_session.rollback()

                creator_data = creator.model_dump()
                mapper = inspect(model)
                table = mapper.local_table

                for constraint in table.constraints:
                    if isinstance(constraint, UniqueConstraint):
                        query = db_session.query(model)

                        all_columns_present = True
                        for column in constraint.columns:
                            if column.name in creator_data:
                                query = query.filter(
                                    getattr(model, column.name) == creator_data[column.name],
                                )
                            else:
                                all_columns_present = False
                                break

                        if all_columns_present:
                            existing = query.one_or_none()
                            if existing:
                                return existing

                # fallback to primary key
                query = db_session.query(model)
                for key in mapper.primary_key:
                    if key.name in creator_data:
                        query = query.filter(getattr(model, key.name) == creator_data[key.name])

                existing = query.one_or_none()
                if existing:
                    return existing

            raise

    return wrapper

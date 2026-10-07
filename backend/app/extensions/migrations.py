"""Database migrations of extensions: each keeps its own Alembic history next to the core's.

An extension's tables and its version table start with ``ext_<name>_``, which the core's
autogenerate skips, so neither history can create or drop the other's tables. An extension's
``migrations/env.py`` is a single call: ``run_env("my_extension", Base.metadata)``.
"""

import re
from typing import Any

from alembic import command, context
from alembic.config import Config
from sqlalchemy import Connection, Engine, MetaData, text

TABLE_PREFIX = "ext_"
_NAME = re.compile(r"[a-z][a-z0-9_]*")
# Serialises the processes that start together (API, workers, beat), so one migrates and the rest find head.
_LOCK_KEY = 7_302_118_543_026_771_041


def table_prefix(name: str) -> str:
    return f"{TABLE_PREFIX}{name}_"


def version_table(name: str) -> str:
    return f"{table_prefix(name)}alembic_version"


def is_core_object(name: str | None, type_: str, parent_names: Any) -> bool:
    """``include_name`` for the core's Alembic env: leaves extension tables out of autogenerate."""
    return type_ != "table" or not (name or "").startswith(TABLE_PREFIX)


def name_error(name: str) -> str | None:
    if _NAME.fullmatch(name):
        return None
    return f"name {name!r} must be a lowercase identifier to prefix its tables"


def upgrade(name: str, script_location: str, engine: Engine) -> None:
    """Bring the extension's schema to head in one transaction; DDL is rolled back on failure."""
    config = Config()
    config.set_main_option("script_location", script_location)
    with engine.begin() as connection:
        connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _LOCK_KEY})
        config.attributes.update(connection=connection, extension_name=name)
        command.upgrade(config, "head")


def run_env(name: str, metadata: MetaData) -> None:
    """Body of an extension's ``migrations/env.py``."""
    if context.is_offline_mode():
        raise RuntimeError("extension migrations do not support offline mode")
    expected = context.config.attributes.get("extension_name", name)
    if expected != name:
        raise RuntimeError(f"env.py migrates {name!r}, but runs for extension {expected!r}")
    prefix = table_prefix(name)
    foreign = sorted(table for table in metadata.tables if not table.startswith(prefix))
    if foreign:
        raise RuntimeError(f"tables of extension {name!r} must start with {prefix!r}: {foreign}")

    connection = context.config.attributes.get("connection")
    if connection is not None:
        _run(connection, name, metadata)
        return
    # Run straight from the alembic CLI, e.g. to autogenerate an extension's revision.
    from app.database import engine

    with engine.begin() as connection:
        _run(connection, name, metadata)


def _run(connection: Connection, name: str, metadata: MetaData) -> None:
    prefix = table_prefix(name)
    context.configure(
        connection=connection,
        target_metadata=metadata,
        version_table=version_table(name),
        include_name=lambda object_name, type_, _: type_ != "table" or (object_name or "").startswith(prefix),
    )
    with context.begin_transaction():
        context.run_migrations()

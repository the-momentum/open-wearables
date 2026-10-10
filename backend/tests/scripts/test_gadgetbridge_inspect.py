import sqlite3
from pathlib import Path

import pytest

from scripts.gadgetbridge_inspect import inspect_database


def test_inventory_contains_schema_and_counts_without_health_values(tmp_path: Path) -> None:
    path = tmp_path / "export.sqlite"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            'CREATE TABLE "quoted""table" (value INTEGER); INSERT INTO "quoted""table" VALUES (67);'
        )
    before = path.read_bytes()
    result = inspect_database(path)
    assert result["tables"]['quoted"table']["rows"] == 1
    assert result["tables"]['quoted"table']["columns"] == [{"name": "value", "type": "INTEGER", "primary_key": 0}]
    assert path.read_bytes() == before


def test_missing_export_is_not_created(tmp_path: Path) -> None:
    path = tmp_path / "missing.sqlite"
    with pytest.raises(sqlite3.OperationalError):
        inspect_database(path)
    assert not path.exists()

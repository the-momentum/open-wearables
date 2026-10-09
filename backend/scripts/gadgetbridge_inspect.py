"""Read-only schema/count inventory; deliberately excludes individual health measurements."""

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


def inspect_database(path: Path) -> dict[str, Any]:
    uri = path.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.execute("PRAGMA query_only=ON")
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        inventory = {}
        for (name,) in tables:
            identifier = '"' + name.replace('"', '""') + '"'
            columns = connection.execute(f"PRAGMA table_info({identifier})").fetchall()
            inventory[name] = {
                "rows": connection.execute(f"SELECT COUNT(*) FROM {identifier}").fetchone()[0],
                "columns": [{"name": row[1], "type": row[2], "primary_key": row[5]} for row in columns],
            }
        return {"user_version": connection.execute("PRAGMA user_version").fetchone()[0], "tables": inventory}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    args = parser.parse_args()
    try:
        result = inspect_database(args.database)
    except sqlite3.Error as error:
        parser.exit(1, f"Cannot inspect SQLite export: {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

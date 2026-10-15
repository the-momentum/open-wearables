"""Guard the Alembic migration chain against changes that make deployed databases skip migrations.

Two checks:

1. ``migrations/versions`` has exactly one head. Two heads mean two branches added a migration
   on the same parent and nobody resolved the conflict yet.
2. No migration that already exists on the base branch has its ``down_revision`` changed, and no
   existing migration is deleted or renamed. Re-pointing an already-merged migration so that a new
   one sits "behind" it looks fine to ``alembic heads``, but every database that already recorded
   the merged revision treats the new migration as an ancestor and never runs it.

The correct way to resolve a two-head conflict is to re-point the migration that is *not* on the
base branch yet, so it becomes the new head: set its ``down_revision`` to the head from the base
branch and rename the file so its date is later than the last migration there. Keep the ``rev`` id.
A dev database that already ran it must be downgraded first and upgraded again afterwards, or it
never applies the migration from the base branch.

Usage (from ``backend/``)::

    uv run python scripts/check_migrations.py [--base origin/main]

Needs only git and the migration files: no database, no application settings.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND_DIR = Path(__file__).resolve().parents[1]
VERSIONS_DIR = "migrations/versions"
DOWN_REVISION_RE = re.compile(r"^down_revision\b.*$", re.MULTILINE)


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _down_revision_line(source: str) -> str | None:
    match = DOWN_REVISION_RE.search(source)
    return match.group(0).strip() if match else None


def check_single_head() -> list[str]:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    heads = ScriptDirectory.from_config(config).get_heads()
    if len(heads) == 1:
        return []
    if not heads:
        return ["no migration head found in migrations/versions"]
    return [
        f"{len(heads)} migration heads found: {', '.join(sorted(heads))}. "
        "Re-point the migration from this branch so its down_revision is the other head.",
    ]


def check_existing_migrations_unchanged(base_ref: str) -> list[str]:
    merge_base = _git("merge-base", base_ref, "HEAD").strip()
    # Compare the merge base with the working tree so the check also works before committing.
    diff = _git("diff", "--name-status", "-M", "--relative", merge_base, "--", VERSIONS_DIR)

    errors: list[str] = []
    for line in diff.splitlines():
        parts = line.split("\t")
        status, paths = parts[0], parts[1:]
        if status.startswith("A"):
            continue
        if status.startswith("D"):
            errors.append(f"{paths[0]}: migration already on {base_ref} was deleted")
            continue
        if status.startswith("R"):
            errors.append(f"{paths[0]}: migration already on {base_ref} was renamed to {paths[1]}")
            continue
        if not status.startswith("M"):
            continue

        path = paths[0]
        before = _down_revision_line(_git("show", f"{merge_base}:./{path}"))
        after = _down_revision_line((BACKEND_DIR / path).read_text())
        if before != after:
            errors.append(
                f"{path}: down_revision changed from `{before}` to `{after}`. "
                f"This migration is already on {base_ref}; databases that applied it will skip "
                "anything inserted before it. Re-point the new migration instead.",
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default="origin/main", help="git ref of the branch the change will merge into")
    args = parser.parse_args()

    errors = check_single_head() + check_existing_migrations_unchanged(args.base)
    if errors:
        print("Migration chain check failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print("Migration chain OK: single head, existing migrations untouched.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

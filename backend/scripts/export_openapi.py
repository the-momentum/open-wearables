"""Export the OpenAPI schema to docs/openapi.json.

The API Reference at docs.openwearables.io is built by Mintlify from this file,
so the published reference always matches the code on `main` and redeploys on
merge like any other docs change. The file is generated, never edited by hand.

Run manually:
    cd backend && uv run python scripts/export_openapi.py

Check without writing (used by CI):
    cd backend && uv run python scripts/export_openapi.py --check

Wired into pre-commit so the spec regenerates whenever a route, schema or
main.py changes.
"""

import json
import sys
import warnings
from pathlib import Path

DOCS_PATH = Path(__file__).resolve().parents[2] / "docs" / "openapi.json"


def render() -> str:
    # FastAPI warns about duplicate operation IDs on routers mounted twice
    # (e.g. Oura webhooks); the schema itself is fine.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        from app.main import api

        schema = api.openapi()
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    check = "--check" in sys.argv[1:]
    content = render()

    if check:
        current = DOCS_PATH.read_text(encoding="utf-8") if DOCS_PATH.exists() else ""
        if current != content:
            print(
                f"{DOCS_PATH.relative_to(DOCS_PATH.parents[1])} is out of date. "
                "Run `cd backend && uv run python scripts/export_openapi.py` and commit the result.",
                file=sys.stderr,
            )
            return 1
        print("OpenAPI spec is up to date.")
        return 0

    DOCS_PATH.write_text(content, encoding="utf-8")
    print(f"Wrote {DOCS_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

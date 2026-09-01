"""Regenerate the auto-generated coverage tables in docs/providers/coverage.mdx.

Single source of truth is ProviderCoverage (via the same _build_coverage() that
feeds /v1/meta/coverage and the frontend Data Coverage tab) — this script just
renders it as markdown between the GENERATED:COVERAGE markers in the docs file.

Run manually:
    cd backend && uv run python scripts/generate_coverage_docs.py

Wired into pre-commit so the docs regenerate whenever a provider's coverage.py
(or base_strategy.py / meta.py) changes.
"""

import re
from pathlib import Path

from app.api.routes.v1.meta import _build_coverage
from app.schemas.model_crud.coverage import (
    CoverageResponse,
    HealthScore,
    MenstrualCycleField,
    SleepField,
    WorkoutField,
)

DOCS_PATH = Path(__file__).resolve().parents[2] / "docs" / "providers" / "coverage.mdx"

# Mintlify's MDX parser rejects raw HTML comments (`<!-- -->`); JSX-style
# comments are required instead.
START_MARKER = "{/* GENERATED:COVERAGE:START */}"
END_MARKER = "{/* GENERATED:COVERAGE:END */}"


def _mark(supported: bool) -> str:
    return "✅" if supported else "❌"


def _provider_headers(providers: list[str]) -> list[str]:
    # Provider slugs (from ProviderName) are single lowercase words — capitalize
    # is a faithful display form, no separate name map to keep in sync.
    return [p.capitalize() for p in providers]


def _render_timeseries_section(coverage: CoverageResponse) -> str:
    lines = ["## Detailed Coverage Matrix", ""]
    for cat in coverage.timeseries:
        lines.append(f"### {cat.name}")
        lines.append("")
        headers = ["Metric", "Unit", *_provider_headers(coverage.providers)]
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("|------|------|" + "|".join(":----:" for _ in coverage.providers) + "|")
        for m in cat.metrics:
            row = [f"`{m.code}`", m.unit, *(_mark(p in m.providers) for p in coverage.providers)]
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_field_section(
    title: str,
    code_header: str,
    fields: list[WorkoutField] | list[SleepField] | list[MenstrualCycleField] | list[HealthScore],
    providers: list[str],
) -> str:
    lines = [f"## {title}", ""]
    headers = [code_header, *_provider_headers(providers)]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|------|" + "|".join(":----:" for _ in providers) + "|")
    for f in fields:
        row = [f"`{f.code}`", *(_mark(p in f.providers) for p in providers)]
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def generate_body(coverage: CoverageResponse) -> str:
    sections = [
        _render_timeseries_section(coverage),
        _render_field_section("Workout Data Coverage", "Field", coverage.workout_fields, coverage.providers),
        _render_field_section("Sleep Data Coverage", "Field", coverage.sleep_fields, coverage.providers),
        _render_field_section("Women's Health Coverage", "Field", coverage.menstrual_cycle_fields, coverage.providers),
        _render_field_section("Health Scores Coverage", "Score", coverage.health_scores, coverage.providers),
    ]
    # Dev-facing note, invisible in the rendered page (reader-facing content has no
    # reason to mention this section is auto-generated). No divider after it — the
    # static template already places a "---" right before the START marker.
    dev_note = (
        "{/* Auto-generated from ProviderCoverage by scripts/generate_coverage_docs.py — do not edit by hand. */}\n"
    )
    return dev_note + "\n" + "\n---\n\n".join(sections)


def main() -> None:
    coverage = _build_coverage()
    body = generate_body(coverage)
    text = DOCS_PATH.read_text()

    pattern = re.compile(re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER), re.DOTALL)
    if not pattern.search(text):
        raise SystemExit(f"Markers {START_MARKER}/{END_MARKER} not found in {DOCS_PATH}")

    replacement = f"{START_MARKER}\n\n{body}\n{END_MARKER}"
    new_text = pattern.sub(replacement, text)
    if new_text != text:
        DOCS_PATH.write_text(new_text)


if __name__ == "__main__":
    main()

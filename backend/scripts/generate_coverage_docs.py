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


def _provider_headers(providers: list[str]) -> list[str]:
    # Provider slugs (from ProviderName) are single lowercase words — capitalize
    # is a faithful display form, no separate name map to keep in sync.
    return [p.capitalize() for p in providers]


def _breakable(code: str) -> str:
    # Long snake_case codes may wrap in the pinned column, but only after an underscore.
    return code.replace("_", "_<wbr />")


def _render_table(
    rows: list[tuple[str, str, list[str]]],
    providers: list[str],
    groups: list[tuple[str, int]] | None = None,
) -> list[str]:
    """Static HTML matrix styled by docs/coverage.css: pinned header + first column,
    rotated provider names, dots instead of emoji. Plain markup keeps the content in
    the page source (SSR, site search, llms.txt) — no client-side component."""
    lines = ['<div className="ow-cov">', '<table className="ow-cov-table">', "<thead>", "<tr>"]
    lines.append(f'<th className="ow-cov-sticky ow-cov-corner">{len(rows)} rows</th>')
    for name in _provider_headers(providers):
        lines.append(f'<th className="ow-cov-provider"><span className="ow-cov-vlabel">{name}</span></th>')
    lines += ["</tr>", "</thead>", "<tbody>"]
    group_starts = {index: name for name, index in (groups or [])}
    for i, (code, unit, supported) in enumerate(rows):
        if i in group_starts:
            lines.append(
                f'<tr className="ow-cov-cat"><td className="ow-cov-sticky">{group_starts[i]}</td>'
                f"<td colSpan={{{len(providers)}}}></td></tr>"
            )
        unit_html = f' <span className="ow-cov-unit">{unit}</span>' if unit else ""
        cells = "".join(f'<td className="{"y" if p in supported else "n"}"></td>' for p in providers)
        metric = f'<td className="ow-cov-sticky ow-cov-metric"><code>{_breakable(code)}</code>{unit_html}</td>'
        lines.append(f"<tr>{metric}{cells}</tr>")
    lines += ["</tbody>", "</table>", "</div>"]
    return lines


def _render_timeseries_tab(coverage: CoverageResponse) -> list[str]:
    rows: list[tuple[str, str, list[str]]] = []
    groups: list[tuple[str, int]] = []
    for cat in coverage.timeseries:
        groups.append((cat.name, len(rows)))
        rows.extend((m.code, m.unit, m.providers) for m in cat.metrics)
    return _render_table(rows, coverage.providers, groups)


def _render_field_tab(
    fields: list[WorkoutField] | list[SleepField] | list[MenstrualCycleField] | list[HealthScore],
    providers: list[str],
) -> list[str]:
    return _render_table([(f.code, "", f.providers) for f in fields], providers)


def generate_body(coverage: CoverageResponse) -> str:
    tabs = [
        ("Timeseries", _render_timeseries_tab(coverage)),
        ("Workout", _render_field_tab(coverage.workout_fields, coverage.providers)),
        ("Sleep", _render_field_tab(coverage.sleep_fields, coverage.providers)),
        ("Women's Health", _render_field_tab(coverage.menstrual_cycle_fields, coverage.providers)),
        ("Health Scores", _render_field_tab(coverage.health_scores, coverage.providers)),
    ]
    lines = [
        # Dev-facing note, invisible in the rendered page.
        "{/* Auto-generated from ProviderCoverage by scripts/generate_coverage_docs.py — do not edit by hand. */}",
        "",
        "## Detailed Coverage Matrix",
        "",
        "<Tabs>",
    ]
    for title, table_lines in tabs:
        lines.append(f'<Tab title="{title}">')
        lines.extend(table_lines)
        lines.append("</Tab>")
    lines += [
        "</Tabs>",
        "",
        '<div className="ow-cov-legend"><span><i className="ow-cov-dot y"></i> supported</span>'
        '<span><i className="ow-cov-dot n"></i> not available</span></div>',
    ]
    return "\n".join(lines) + "\n"


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

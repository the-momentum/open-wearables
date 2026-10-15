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
    MealField,
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
    # Slugs are lowercase, some underscore-separated — title-casing each word is a
    # faithful display form, no separate name map to keep in sync.
    return [" ".join(word.capitalize() for word in p.split("_")) for p in providers]


# (code, unit, providers that support it)
Row = tuple[str, str, list[str]]
# Rows split under optional category headings (timeseries has them, field tables don't).
Groups = list[tuple[str | None, list[Row]]]

_STATUS_TEXT = {"y": "Supported", "n": "Not available"}


def _breakable(code: str) -> str:
    # Long snake_case codes may wrap in the pinned column, but only after an underscore.
    return code.replace("_", "_<wbr />")


def _render_html_table(groups: Groups, providers: list[str]) -> list[str]:
    """Static HTML matrix styled by docs/coverage.css: pinned header + first column,
    rotated provider names, dots instead of emoji. Each cell also carries visually
    hidden status text so screen readers get the same information as the dots."""
    lines = ['<div className="ow-cov">', '<table className="ow-cov-table">', "<thead>", "<tr>"]
    row_count = sum(len(rows) for _, rows in groups)
    lines.append(f'<th className="ow-cov-sticky ow-cov-corner">{row_count} rows</th>')
    for name in _provider_headers(providers):
        lines.append(f'<th className="ow-cov-provider"><span className="ow-cov-vlabel">{name}</span></th>')
    lines += ["</tr>", "</thead>", "<tbody>"]
    for group_name, rows in groups:
        if group_name:
            lines.append(
                f'<tr className="ow-cov-cat"><td className="ow-cov-sticky">{group_name}</td>'
                f"<td colSpan={{{len(providers)}}}></td></tr>"
            )
        for code, unit, supported in rows:
            unit_html = f' <span className="ow-cov-unit">{unit}</span>' if unit else ""
            metric_html = f"<code>{_breakable(code)}</code>{unit_html}"
            metric = f'<th scope="row" className="ow-cov-sticky ow-cov-metric">{metric_html}</th>'
            cells = "".join(
                f'<td className="{s}"><span className="ow-cov-sr">{_STATUS_TEXT[s]}</span></td>'
                for s in ("y" if p in supported else "n" for p in providers)
            )
            lines.append(f"<tr>{metric}{cells}</tr>")
    lines += ["</tbody>", "</table>", "</div>"]
    return lines


def _render_markdown_tables(groups: Groups, providers: list[str], code_header: str) -> list[str]:
    """Plain markdown tables for the agent-facing copy (.md page views, llms-full.txt),
    where the HTML matrix would come through as empty cells."""
    with_unit = any(unit for _, rows in groups for _, unit, _ in rows)
    label_headers = [code_header, *(["Unit"] if with_unit else [])]
    header_row = "| " + " | ".join([*label_headers, *_provider_headers(providers)]) + " |"
    separator = "|" + "|".join(["------"] * len(label_headers) + [":----:"] * len(providers)) + "|"
    lines: list[str] = []
    for group_name, rows in groups:
        if group_name:
            lines += [f"**{group_name}**", ""]
        lines += [header_row, separator]
        for code, unit, supported in rows:
            row = [f"`{code}`", *([unit] if with_unit else []), *("✅" if p in supported else "❌" for p in providers)]
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")
    return lines


def _field_groups(
    fields: list[WorkoutField] | list[SleepField] | list[MenstrualCycleField] | list[MealField] | list[HealthScore],
) -> Groups:
    return [(None, [(f.code, "", f.providers) for f in fields])]


def generate_body(coverage: CoverageResponse) -> str:
    timeseries: Groups = [
        (cat.name, [(m.code, m.unit, m.providers) for m in cat.metrics]) for cat in coverage.timeseries
    ]
    # (title, code column header, rows)
    sections: list[tuple[str, str, Groups]] = [
        ("Timeseries", "Metric", timeseries),
        ("Workout", "Field", _field_groups(coverage.workout_fields)),
        ("Sleep", "Field", _field_groups(coverage.sleep_fields)),
        ("Women's Health", "Field", _field_groups(coverage.menstrual_cycle_fields)),
        ("Meals", "Field", _field_groups(coverage.meal_fields)),
        ("Health Scores", "Score", _field_groups(coverage.health_scores)),
    ]
    providers = coverage.providers
    lines = [
        # Dev-facing note, invisible in the rendered page.
        "{/* Auto-generated from ProviderCoverage by scripts/generate_coverage_docs.py — do not edit by hand. */}",
        "",
        "## Detailed Coverage Matrix",
        "",
        # Humans get the compact HTML matrix; agents (.md views, llms-full.txt) get markdown tables.
        '<Visibility for="humans">',
        "<Tabs>",
    ]
    for title, _, groups in sections:
        lines.append(f'<Tab title="{title}">')
        lines.extend(_render_html_table(groups, providers))
        lines.append("</Tab>")
    lines += [
        "</Tabs>",
        "",
        '<div className="ow-cov-legend"><span><i className="ow-cov-dot y"></i> supported</span>'
        '<span><i className="ow-cov-dot n"></i> not available</span></div>',
        "</Visibility>",
        "",
        '<Visibility for="agents">',
        "Legend: ✅ supported, ❌ not available.",
        "",
    ]
    for title, code_header, groups in sections:
        lines += [f"**{title} coverage**", ""]
        lines.extend(_render_markdown_tables(groups, providers, code_header))
    lines.append("</Visibility>")
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

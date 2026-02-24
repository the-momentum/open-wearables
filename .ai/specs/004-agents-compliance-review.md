# AGENTS.md Compliance Review

Automated PR review that evaluates code changes against `AGENTS.md` guidelines using Claude Code Action, with aggregated violation tracking in a pinned GitHub Issue.

## Architecture

```
PR opened/ready_for_review
        |
        v
+---------------------+
| Claude Code Action   |
| - reads PR diff      |
| - reads AGENTS.md    |
|   files as source    |
|   of truth           |
| - posts inline       |
|   comments (max 10)  |
| - posts summary      |
|   comment with JSON  |
+---------+-----------+
          |
          v
+---------------------+
| Update tracking step |
| - finds summary      |
|   comment via gh api |
| - parses JSON        |
| - merges counts      |
| - updates pinned     |
|   issue body         |
+---------------------+
```

## Components

### Workflow: `.github/workflows/agents-instructions-evaluation.yml`

- **Trigger**: `pull_request` (opened, ready_for_review) on `backend/**` or `frontend/**` paths
- **Manual trigger**: `workflow_dispatch` with PR number for re-review
- **Concurrency**: one review per PR, cancel-in-progress

### Claude Code Action step

- Uses `anthropics/claude-code-action@v1` with Sonnet model
- Reads AGENTS.md files dynamically (no hardcoded rules in the workflow)
- Posts inline comments on violations (max 10)
- Posts a summary comment with a hidden JSON marker for machine parsing

### Tracking step

- Parses the `<!-- AGENTS_REVIEW_SUMMARY {...} -->` marker from summary comment
- Merges violation counts into a pinned GitHub Issue
- Uses Python script (stdlib only) for JSON parsing and issue body generation

## Setup requirements

| Step | Action |
|------|--------|
| 1 | Add `ANTHROPIC_API_KEY` secret (Settings > Secrets > Actions) |
| 2 | Create pinned issue "AGENTS.md Compliance Report" with label `compliance-tracker` |
| 3 | Save issue number as `COMPLIANCE_ISSUE_NUMBER` variable (Settings > Variables > Actions) |

### Initial issue body

```markdown
# AGENTS.md Compliance Report

Last updated: -
Total PRs reviewed: 0

## Backend violations
| Rule | Count | Last seen |
|------|-------|-----------|

## Frontend violations
| Rule | Count | Last seen |
|------|-------|-----------|
```

## Design decisions

| Decision | Rationale |
|----------|-----------|
| `opened` + `ready_for_review` (not `synchronize`) | Once per PR, not every push - cost control |
| `workflow_dispatch` fallback | Manual re-review after PR changes |
| `concurrency: cancel-in-progress` | Cancels old run if new one triggers |
| Sonnet model (not Opus) | Sufficient for pattern matching vs rules, ~10x cheaper |
| `--max-turns 8` | Enough for diff read + AGENTS.md reads + inline comments + summary |
| AGENTS.md as sole source of truth | No hardcoded rules in workflow - stays in sync automatically |
| Hidden JSON in HTML comment | Machine-parseable without cluttering the visible comment |
| Python script for merge (stdlib only) | Simple, readable, no extra dependencies |
| Pinned issue as dashboard | Single visible location in repo, auto-updated |

## Estimated cost

- ~$0.05-0.15 per review (Sonnet)
- 1 automatic review per PR (on open) + optional manual re-review

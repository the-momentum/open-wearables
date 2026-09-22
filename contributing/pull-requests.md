# Pull Request Guidelines

This guide covers how to submit pull requests to Open Wearables.

## Before You Start

1. Search [existing PRs](https://github.com/the-momentum/open-wearables/pulls) to avoid duplicating effort
2. Check [existing issues](https://github.com/the-momentum/open-wearables/issues) for related discussions
3. For major changes, open an issue first to discuss the approach

## Commit Message Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/).

### Types

| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation changes |
| `chore` | Maintenance tasks |
| `refactor` | Code refactoring (no functional change) |
| `test` | Adding or updating tests |
| `style` | Formatting changes |
| `perf` | Performance improvements |
| `ci` | CI/CD changes |

## PR Title Convention

**PR titles must follow the same [Conventional Commits](https://www.conventionalcommits.org/) format as commit messages.**

The CI workflow automatically validates PR titles to ensure they follow this convention. Your PR title should use the format:

```
<type>(<optional scope>): <description>
```

### Examples

- `feat: add user profile endpoint`
- `fix(auth): resolve token refresh issue`
- `docs: update API documentation`
- `ci: add PR title validation to workflow`
- `refactor(backend): simplify authentication logic`


## Filling In the PR Template

Opening a PR gives you a template asking what changed, why, how you tested it, and what AI you used. Please answer it.

**Aim for a description that says something the diff doesn't.** A summary of the changes is the least useful thing you can write, because that's the one part we can already see. Your reasoning, your rejected alternatives and your open questions are what make a review fast. You're welcome to use an AI to help you put it into words - just make sure the substance is yours. See [AI-assisted contributions](../CONTRIBUTING.md#ai-assisted-contributions).

## Showing That It Works

"How did you test this?" is the part of the template we read most carefully. The bar: a reviewer should be able to believe the claim without checking out the branch. Two things get you there - what you ran, and what you saw.

The patterns below are examples of what has worked well in this repo, not a checklist. If a different format shows your change better, use that.

**Behaviour change or bug fix - show before and after.** The exact request and the response, trimmed to the fields that make the point.

```
# POST /token/refresh with a refresh token issued before the password change
Before: HTTP 200 {"access_token": "<redacted>", ...}
After:  HTTP 401 {"detail": "Invalid or revoked refresh token"}
```
See [#1590](https://github.com/the-momentum/open-wearables/pull/1590), [#1630](https://github.com/the-momentum/open-wearables/pull/1630).

**New parameter or endpoint - one request per claim.** Every sentence in the description that says the endpoint "now does X" gets a request that shows X. Include the edge cases: invalid value, empty result, an ID that belongs to another user.

```
provider=fitbit_XX                         -> 400
data_source_id=abc                         -> 400 (not a UUID)
data_source_id belonging to another user   -> 200, [] , total_count 0
```
See [#1626](https://github.com/the-momentum/open-wearables/pull/1626), [#1628](https://github.com/the-momentum/open-wearables/pull/1628), [#1557](https://github.com/the-momentum/open-wearables/pull/1557).

**Performance or resource fix - numbers in a table, with the conditions.** Before vs after, plus enough context to judge the numbers: data size, concurrency, config.

| stream auth | connections held (8 concurrent streams) |
|---|---|
| `ApiKeyDep` | 8 `idle in transaction` |
| `StreamingApiKeyDep` | 0 |

See [#1565](https://github.com/the-momentum/open-wearables/pull/1565), [#1628](https://github.com/the-momentum/open-wearables/pull/1628) (query cost section).

**Docs or UI - a screenshot.** Of the rendered page or the screen after the change, not of the source.
See [#1595](https://github.com/the-momentum/open-wearables/pull/1595), [#1621](https://github.com/the-momentum/open-wearables/pull/1621).

**Provider integrations - a real account.** Tell us which provider account you synced against and paste the relevant part of the response or the log, redacted.

### Say what you did not test

Please don't open PRs you haven't been able to run at all. Review is our bottleneck, and if we have to reproduce the bug, run your change and check the result ourselves, we're doing most of the work anyway. If there's something you genuinely can't test - no provider account, no device, a step only someone else can do - say so on the issue first or mark the PR as a draft and spell out what's missing. "I couldn't check X because Y" is fine. Leaving the question blank isn't.

### Keep it short

Trim JSON to the fields that make the point, drop the rest. Strip secrets and personal data. The headings in the template are a suggestion - "Before / After" or "Cost" as your own sections is fine if it reads better.

## Linking Issues

Link related issues in your PR description:

- `Fixes #123` - Closes the issue when PR is merged
- `Closes #456` - Same as Fixes
- `Relates to #789` - References without closing

## Code Review Process

See [Code Review Process](../CONTRIBUTING.md#code-review-process) in the contributing guide.

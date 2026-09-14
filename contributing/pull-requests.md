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

## Linking Issues

Link related issues in your PR description:

- `Fixes #123` - Closes the issue when PR is merged
- `Closes #456` - Same as Fixes
- `Relates to #789` - References without closing

## Code Review Process

See [Code Review Process](../CONTRIBUTING.md#code-review-process) in the contributing guide.

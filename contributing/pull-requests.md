# Pull Request Guidelines

This guide covers how to submit pull requests to Open Wearables.

## Before You Start

1. Search [existing PRs](https://github.com/open-wearables/open-wearables/pulls) to avoid duplicating effort
2. Check [existing issues](https://github.com/open-wearables/open-wearables/issues) for related discussions
3. For major changes, open an issue first to discuss the approach

## Branch Naming

Use this format: `<issue-number>-<brief-description>`

Examples:
- `123-fix-user-authentication`
- `456-add-garmin-provider`
- `789-update-dashboard-layout`

## Commit Message Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<optional scope>): <description>

[optional body]

[optional footer]
```

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

### Examples

```bash
# Simple commit
feat: add user profile endpoint

# With scope
fix(auth): resolve token refresh issue

# With ticket reference
[WHOOP-01] feat: implement Whoop provider integration

# With body
feat(api): add pagination to workouts endpoint

Adds limit and offset parameters to support
pagination in the workouts list endpoint.

Closes #123
```

## Creating a Pull Request

1. **Create a branch** from `main`:
   ```bash
   git checkout -b 123-your-feature-description
   ```

2. **Make your changes** and commit following the conventions above

3. **Push your branch**:
   ```bash
   git push -u origin 123-your-feature-description
   ```

4. **Open a PR** on GitHub and fill out the template

## PR Checklist

The PR template includes these requirements:

### General
- [ ] Code follows the project's code style
- [ ] Self-review completed
- [ ] Tests added (if applicable)
- [ ] All tests pass locally

### Backend Changes
- [ ] `uv run ruff check` passes
- [ ] `uv run ruff format --check` passes
- [ ] `uv run ty check` passes

### Frontend Changes
- [ ] `pnpm run lint` passes
- [ ] `pnpm run format:check` passes
- [ ] `pnpm run build` succeeds

## Linking Issues

Link related issues in your PR description:

- `Fixes #123` - Closes the issue when PR is merged
- `Closes #456` - Same as Fixes
- `Relates to #789` - References without closing

## Code Review Process

1. **Request review**: PRs require at least one approval
2. **Address feedback**: Respond to comments and make requested changes
3. **CI must pass**: All automated checks must be green
4. **Merge**: Once approved, the PR can be merged

## Tips for a Good PR

- Keep PRs focused and reasonably sized
- Write a clear description of what and why
- Include screenshots for UI changes
- Update documentation if needed
- Add tests for new functionality

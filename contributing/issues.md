# Reporting Issues

This guide covers how to report bugs and request features for Open Wearables.

## Before Creating an Issue

1. **Search existing issues** - Your issue may already be reported at [GitHub Issues](https://github.com/open-wearables/open-wearables/issues)
2. **Check closed issues** - The issue may have been resolved in a recent update
3. **Update to latest** - Ensure you're running the latest version

## Bug Reports

When reporting a bug, include:

### Required Information

- **Description**: Clear, concise description of the bug
- **Steps to Reproduce**: Numbered steps to reproduce the issue
- **Expected Behavior**: What you expected to happen
- **Actual Behavior**: What actually happened

### Helpful Information

- **Environment**: OS, browser, Node.js/Python version
- **Screenshots**: If applicable, add screenshots
- **Error Messages**: Include any error logs or stack traces
- **Related Configuration**: Relevant settings or environment variables

### Bug Report Template

```markdown
## Description
[Clear description of the bug]

## Steps to Reproduce
1. Go to '...'
2. Click on '...'
3. See error

## Expected Behavior
[What you expected to happen]

## Actual Behavior
[What actually happened]

## Environment
- OS: [e.g., macOS 14.0]
- Browser: [e.g., Chrome 120]
- Node.js: [e.g., 20.10.0]
- Python: [e.g., 3.13.0]

## Additional Context
[Any other relevant information]
```

## Feature Requests

When requesting a feature, include:

### Required Information

- **Problem Statement**: What problem does this solve?
- **Proposed Solution**: How would you like it to work?
- **Use Case**: Who would benefit and how?

### Feature Request Template

```markdown
## Problem Statement
[Description of the problem or need]

## Proposed Solution
[How you'd like this to work]

## Use Case
[Who benefits and in what scenario]

## Alternatives Considered
[Other solutions you've thought about]

## Additional Context
[Any other relevant information]
```

## Issue Labels

Common labels you may see:

| Label | Description |
|-------|-------------|
| `bug` | Something isn't working |
| `feature` | New feature request |
| `documentation` | Documentation improvements |
| `good first issue` | Good for newcomers |
| `help wanted` | Extra attention needed |
| `backend` | Related to Python/FastAPI |
| `frontend` | Related to React/TypeScript |

## Getting Help

If you need help but it's not a bug or feature request:

- Check the [documentation](../README.md)
- Review the [API docs](http://localhost:8000/docs) when running locally
- Ask in discussions or community channels

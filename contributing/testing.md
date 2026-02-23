# Testing

This guide covers how to run tests and write new tests for Open Wearables.

## Prerequisites

- **Docker daemon** must be running (testcontainers spins up a disposable Postgres automatically).
- `uv` installed.
- Backend dev dependencies: `cd backend && uv sync --dev`

## Running Tests

### Backend Tests

```bash
# Using Make (recommended)
make test

# Or directly with pytest
cd backend
uv run pytest

# Run specific test file
uv run pytest tests/api/v1/test_users.py

# Run with verbose output
uv run pytest -v

# Run with coverage report
uv run pytest --cov=app --cov-report=html
```

### Frontend Tests

```bash
cd frontend

# Run all tests
pnpm test

# Run tests in watch mode
pnpm test:watch

# Run specific test file
pnpm test src/components/Button.test.tsx
```

## Writing Tests

### Backend Tests

Backend tests use **pytest** with **pytest-asyncio** for async support.

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_get_users(client: AsyncClient):
    response = await client.get("/api/v1/users")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

Test files should be placed in the `backend/tests/` directory and named with `test_` prefix.

### Frontend Tests

Frontend tests use **Vitest** with **React Testing Library**.

```typescript
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { Button } from './Button';

describe('Button', () => {
  it('renders correctly', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole('button')).toHaveTextContent('Click me');
  });
});
```

Test files should be colocated with components using `.test.tsx` or `.test.ts` suffix.

## Test Requirements

- All new features should include tests
- Bug fixes should include a test that would have caught the bug
- Tests must pass before a PR can be merged
- Aim for meaningful test coverage, not just high percentages

**Note:** Tests use transaction rollback for isolation - each test runs in its own transaction that is rolled back after the test completes. This ensures tests don't interfere with each other.

## Testing Patterns

For more detailed testing patterns, see:

- [Backend AGENTS.md](../backend/AGENTS.md) - Backend testing conventions
- [Frontend AGENTS.md](../frontend/AGENTS.md) - Frontend testing patterns

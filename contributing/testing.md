# Testing

This guide covers how to run tests and write new tests for Open Wearables.

## Prerequisites

Tests use [testcontainers](https://testcontainers.com/guides/getting-started-with-testcontainers-for-python/) to automatically spin up a disposable PostgreSQL container. You need:

- **Docker running** on your machine
- **No manual database setup required** — testcontainers handles everything automatically

> **CI note:** In GitHub Actions the workflow provides its own PostgreSQL service and sets `TEST_DATABASE_URL`. When that variable is present, testcontainers is skipped and the external database is used directly.

## Running Tests

### Backend Tests

```bash
# Using Make (recommended; run from project root directory)
make test

# Or directly with pytest (run `uv sync --dev` first)
cd backend
uv run pytest

# Run specific test file
uv run pytest tests/api/v1/test_users.py

# Run with verbose output
uv run pytest -v
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

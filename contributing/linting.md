# Code Style & Linting

This guide covers code formatting and linting for Open Wearables.

## Quick Start

The project uses **pre-commit hooks** to run all checks automatically. This is the recommended way to ensure your code passes all checks:

```bash
# Run all checks (from project root)
uv run pre-commit run --all-files
```

This runs:
- Ruff linter with auto-fix
- Ruff formatter
- ty type checker
- Trailing whitespace removal
- End-of-file fixer

## Backend (Python)

We use **Ruff** for linting and formatting, and **ty** for type checking.

### Individual Commands

If you need to run checks individually:

```bash
cd backend

# Check for linting errors
uv run ruff check .

# Fix linting errors automatically
uv run ruff check . --fix

# Check formatting
uv run ruff format --check .

# Apply formatting
uv run ruff format .

# Type checking
uv run ty check .
```

### Style Guidelines

- **Line length**: 120 characters
- **Type hints**: Required on all function parameters and return types
- **Imports**: Sorted automatically by Ruff

## Frontend (TypeScript/React)

We use **oxlint** for linting and **Prettier** for formatting.

### Commands

```bash
cd frontend

# Check for linting errors
pnpm lint

# Fix linting errors
pnpm lint:fix

# Check formatting
pnpm format:check

# Apply formatting
pnpm format
```

### Style Guidelines

- **Line length**: 80 characters
- **Quotes**: Single quotes
- **Semicolons**: Required
- **TypeScript**: Strict mode enabled

### Before Submitting a PR

Run all checks:

```bash
cd frontend
pnpm lint:fix && pnpm format
```

## CI Checks

The CI pipeline runs these checks automatically:

**Backend:**
- `uv run ruff check` - Linting
- `uv run ruff format --check` - Formatting
- `uv run ty check` - Type checking

**Frontend:**
- `pnpm run lint` - Linting
- `pnpm run format:check` - Formatting
- `pnpm run build` - Build verification

All checks must pass before a PR can be merged.

## Editor Setup

### VS Code

Recommended extensions:
- **Python**: Ruff extension for auto-formatting
- **TypeScript**: Prettier extension with format-on-save

### Pre-commit Hooks

The project uses pre-commit hooks to run checks automatically before each commit:

```bash
# Install pre-commit hooks (first time only, from project root)
uv sync --group code-quality
uv run pre-commit install

# Run all checks manually
uv run pre-commit run --all-files
```

See `.pre-commit-config.yaml` for the full hook configuration.

## More Information

For detailed style guidelines, see:
- [Backend AGENTS.md](../backend/AGENTS.md) - Backend code conventions
- [Frontend AGENTS.md](../frontend/AGENTS.md) - Frontend code conventions

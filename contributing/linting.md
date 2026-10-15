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

## Frontend (SvelteKit/TypeScript)

We use **ESLint** for linting, **Prettier** for formatting and **svelte-check** for types.

### Commands

```bash
cd frontend

# Check for linting errors
bun run lint

# Type-check
bun run check

# Check formatting
bun run format:check

# Apply formatting
bun run format
```

### Style Guidelines

- **Line length**: 100 characters
- **Indentation**: Tabs
- **Quotes**: Single quotes
- **TypeScript**: Strict mode enabled

### Before Submitting a PR

Run everything CI runs, from the repository root:

```bash
make frontend_verify
```

## CI Checks

The CI pipeline runs these checks automatically:

**Backend:**
- `uv run ruff check` - Linting
- `uv run ruff format --check` - Formatting
- `uv run ty check` - Type checking

**Frontend:**
- `bun run check` - Type checking
- `bun run lint` - Linting
- `bun run format:check` - Formatting
- `bun run build` - Build verification
- `bun run test:unit` and `playwright test` - Unit, component and end-to-end tests

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

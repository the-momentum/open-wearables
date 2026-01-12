# Open Wearables

Open Wearables is a health/wearable data aggregation platform with a Python/FastAPI backend and React/TypeScript frontend.

## Documentation Structure

- **This file** - Project overview, development workflow, general guidelines
- **[backend/AGENTS.md](backend/AGENTS.md)** - Backend-specific patterns and code examples
- **[frontend/AGENTS.md](frontend/AGENTS.md)** - Frontend-specific patterns and code examples
- **[docs/dev-guides/how-to-add-new-provider.mdx](docs/dev-guides/how-to-add-new-provider.mdx)** - Adding wearable providers

## Project Structure

```
open-wearables/
├── backend/           # Python/FastAPI backend
├── frontend/          # React/TypeScript frontend
└── docs/              # Documentation (Mintlify)
```

## Tech Stack

| Backend | Frontend |
|---------|----------|
| Python 3.13+ | React 19 + TypeScript |
| FastAPI | TanStack Router/Query |
| SQLAlchemy 2.0 | React Hook Form + Zod |
| PostgreSQL | Tailwind + shadcn/ui |
| Celery + Redis | Vitest |
| Ruff | oxlint + Prettier |

## Development Workflow

### Docker (Recommended)

```bash
# Start all services
docker compose up -d

# Seed sample data (admin@admin.com / secret123)
make init

# View logs
docker compose logs -f app

# Stop
make stop
```

### Access Points
- Frontend: http://localhost:3000
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Celery Flower: http://localhost:5555

### Makefile Commands

| Command | Description |
|---------|-------------|
| `make build` | Build Docker images |
| `make run` | Start in detached mode |
| `make up` | Start in foreground |
| `make stop` | Stop containers |
| `make down` | Remove containers |
| `make test` | Run backend tests |
| `make migrate` | Apply database migrations |
| `make create_migration m="..."` | Create new migration |
| `make init` | Seed sample data |

### Code Quality

**Backend:**
```bash
cd backend && uv run ruff check . --fix && uv run ruff format .
```

**Frontend:**
```bash
cd frontend && pnpm run lint:fix && pnpm run format
```

## Guidelines for AI Agents

1. **Read specialized docs** - See `backend/AGENTS.md` and `frontend/AGENTS.md` for patterns
2. **Never commit secrets** - Check for .env files, API keys, credentials
3. **Follow existing patterns** - Match the code style of surrounding files
4. **Run quality checks** - Always run lint/format after changes
5. **Use type hints** - All Python functions must have type annotations
6. **Test your changes** - Run relevant tests before considering work complete

## Documentation Standards (docs/)

When working on documentation in the `docs/` directory:

### Code Examples
- Include complete, runnable examples users can copy and execute
- Show proper error handling and edge case management
- Use realistic data instead of placeholder values
- Include expected outputs for verification
- Specify language and include filename when relevant
- Never include real API keys or secrets

### API Documentation
- Document all parameters including optional ones with clear descriptions
- Show both success and error response examples with realistic data
- Include rate limiting information with specific limits
- Provide authentication examples showing proper format
- Explain all HTTP status codes and error handling

### Accessibility
- Include descriptive alt text for all images and diagrams
- Use specific, actionable link text instead of "click here"
- Ensure proper heading hierarchy starting with H2
- Structure content for easy scanning with headers and lists

### Mintlify Component Selection
- **Steps** - For procedures and sequential instructions
- **Tabs** - For platform-specific content or alternative approaches
- **CodeGroup** - For showing same concept in multiple programming languages
- **Accordions** - For progressive disclosure of information
- **RequestExample/ResponseExample** - For API endpoint documentation
- **ParamField** - For API parameters, **ResponseField** - For API responses
- **Expandable** - For nested object properties or hierarchical information

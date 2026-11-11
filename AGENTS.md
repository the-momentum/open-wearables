# Open Wearables

Open Wearables is a health/wearable data aggregation platform with a Python/FastAPI backend and a SvelteKit developer portal.

## Documentation Structure

- **This file** - Project overview, development workflow, general guidelines
- **[backend/AGENTS.md](backend/AGENTS.md)** - Backend-specific patterns and code examples
- **[frontend/AGENTS.md](frontend/AGENTS.md)** - Frontend architecture, testing, and review rules
- **[mcp/README.md](mcp/README.md)** - MCP server setup and available tools
- **[docs/dev-guides/how-to-add-new-provider.mdx](docs/dev-guides/how-to-add-new-provider.mdx)** - Adding wearable providers

## Project Structure

```
open-wearables/
├── backend/           # Python/FastAPI backend
├── frontend/          # SvelteKit developer portal
├── mcp/               # MCP server for AI assistants
└── docs/              # Documentation (Mintlify)
```

## Tech Stack

| Backend | Frontend | MCP |
|---------|----------|-----|
| Python 3.14+ | SvelteKit 2 + Svelte 5 + TypeScript | Python 3.13+ |
| FastAPI | Bun | FastMCP |
| SQLAlchemy 2.0 | Tailwind CSS v4 | httpx |
| PostgreSQL | | |
| Celery + Redis | Vitest + Playwright | |
| Ruff + ty | ESLint + Prettier | Ruff + ty |

## Development Workflow

### Docker (Recommended)

```bash
# Start all services
docker compose up -d

# Admin account and series type definitions are auto-created on startup (admin@admin.com / your-secure-password)
# Seed sample test data (optional)
make seed

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
| `make seed` | Seed sample data |
| `make frontend_verify` | Run every frontend check CI runs |

### Code Quality

**Backend:**
```bash
cd backend && uv run pre-commit run --all-files
```

**Frontend:**
```bash
cd frontend && bun run format && bun run lint && bun run check
```

### Database Migrations

When you rebase and `main` gained a migration in the meantime, `alembic heads` shows two heads. Resolve it by moving **your** migration to the end of the chain. Never touch a migration that is already on `main`: databases that applied it treat everything inserted before it as already done and skip it silently.

1. Set `down_revision` of your migration to the head from `main`.
2. Rename your file so its date is later than the last migration on `main`. Keep the `rev` id. If your dev database already ran this migration, run `make downgrade` before re-pointing and `make migrate` after; otherwise the database keeps your revision as current and never applies the migration from `main`.
3. CI checks the chain and fails on a second head, on a changed `down_revision` in a migration already on `main`, and on a deleted or renamed migration.

## Guidelines for AI Agents

1. **Read specialized docs** - See `backend/AGENTS.md` and `frontend/AGENTS.md` for patterns
2. **Never commit secrets** - Check for .env files, API keys, credentials
3. **Follow existing patterns** - Match the code style of surrounding files
4. **Run quality checks** - Always run lint/format after changes
5. **Use type hints** - All Python functions must have type annotations
6. **Test your changes** - Run relevant tests before considering work complete
7. **Update documentation** - When adding or changing endpoints, providers, API contracts, or features that integrators or operators can see or have to configure, update the relevant pages in `docs/`. Internal mechanisms (token handling, background tasks, tables that don't change the API) don't need docs
8. **Update API Reference navigation** - When adding, removing, or renaming **external** API endpoints (tagged `External: *`), update the `API Reference` tab in `docs/docs.json` to keep the endpoint list in sync
9. **Think beyond the current feature** - Before adding provider-specific or otherwise narrow logic, ask whether the same behavior will be needed elsewhere (other providers, entities). If likely, propose a shared abstraction upfront instead of a one-off implementation.

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

## Fork agent skills

Fork-specific playbooks live in `.agents/skills/`. Before starting work, check
there for a skill that matches the request, and follow its `SKILL.md`.

- **Supporting a new provider.** Read and follow
  `.agents/skills/support-new-provider/SKILL.md` before any request to support,
  add, integrate or review a wearable or health-data provider that upstream does
  not ship (e.g. "support COROS in our open wearables fork"), and during every
  upstream sync (rule 9 below).

## Fork-wins rules (upstream sync guardrails)

This repo is the `frontbacklabs/open-wearables` fork of `the-momentum/open-wearables`,
merged from upstream periodically. The rules below record deliberate fork divergences.
**On every upstream merge and every review or edit touching these areas, preserve them —
do not silently adopt upstream's version.** When upstream lands a feature that conflicts
with a fork rule, gate or adapt the feature rather than dropping the rule.

1. **String user IDs.** `User.id` and `FKUser` stay `Mapped[str]`/`String(255)` — the
   canonical ID is a raw Firebase UID, never a `UUID`. New upstream code that arrives
   with `user_id: UUID` annotations or `UUID(user_id)` conversions must be str-ified in
   app code and tests (`str(uuid4())` / `fake_firebase_uid()`). Several upstream tests
   assume UUID ids and are expected to fail on the fork rather than be "fixed" by
   widening the model.
2. **ECR base images.** `backend/Dockerfile` (and worker/beat) use
   `public.ecr.aws/docker/library/python`, not upstream's Docker Hub base.
   `frontend/Dockerfile` uses ECR `node:22-alpine` + `npm i -g bun@1.4`. Take upstream's
   version bumps (e.g. Python 3.14) but keep the ECR bases.
3. **Google Health scopes stay trimmed.** `google_default_scope` in `backend/app/config.py`
   requests only `openid email`, `activity_and_fitness.readonly`,
   `health_metrics_and_measurements.readonly`, and `sleep.readonly`.
   `nutrition.readonly` and `settings.readonly` are deliberately absent — they were
   removed to keep Google OAuth verification surface minimal. Upstream features that
   call endpoints under a scope we do not grant (e.g. nutrition-log, hydration-log)
   must be gated on the connection's granted scope and skipped when ungranted — see
   `scope_granted()` in `google_health/helpers.py`. Re-adding a scope is a product
   decision, not a merge accident.
4. **API-key auth and Svix.** `api_key_service.py` stays synchronous `def`
   (`_authenticate`, `_require_api_key`, `_require_api_key_detached`) — no `await`
   call sites. Outgoing webhooks stay disabled by default; the self-hosted Svix
   server wiring and the `ENV: test` CI block stay intact.
5. **Ren branding.** Ren logotype (`frontend/src/lib/assets/logotype.svg` driving
   `Wordmark.svelte`), nav **Overview** (not Dashboard), titles `Ren — Open Wearables
   Platform` / `· Ren`, fork login copy, and fork favicons win over upstream branding.
   `sort_order` stays on summaries and their service layer.
6. **No fork migration is ever deleted**, and never edit a migration already on `main`.
   Two alembic heads after a sync are resolved with a new merge revision at the end
   of the chain (see `81ea20b3c94c`), not by repointing an existing revision.
7. **`app.sh` startup.** No `alembic upgrade head` at container start; keep the
   `$PORT` fallback. Upstream additions (extension install, data-migration scripts,
   `exec`) are fine to adopt alongside.
8. **Sleep latency.** `sleep_latency_seconds` is a fork-only field: the
   `sleep_details` column and its migration, `SleepSummary.sleep_latency_seconds`,
   the summaries-service population from the longest main-sleep session, the Oura
   ingest that fills it (`providers/oura/data_247.py`, `coverage.py`), and the
   event-record merge logic that preserves it. Upstream has no equivalent field —
   keep it through merges rather than resolving conflicts toward upstream's shape.
9. **Fork-only providers.** Providers listed in
   `.agents/skills/support-new-provider/fork-providers.json` exist only in the fork.
   An upstream sync must not overwrite, drop or break anything they need: their
   owned files, every shared-file line marked `fork-provider: <slug>`, and their
   `buildspec.yml` wiring. Keep our lines in conflicts (never take a shared file
   wholesale with `--theirs`), and adapt the provider to upstream API changes
   instead of dropping it. **The one exception:** once the upstream ref being
   merged natively supports the provider (a `ProviderName` member plus a
   strategy or factory case), upstream's implementation replaces ours. Run
   `python3 .agents/skills/support-new-provider/scripts/fork_providers.py verify`
   before and after every upstream merge. The preserve and adoption procedures are
   in `.agents/skills/support-new-provider/references/upstream-sync.md`.

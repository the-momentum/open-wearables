# Open Wearables MCP Server

MCP (Model Context Protocol) server for Open Wearables, enabling AI assistants like Claude Desktop, Cursor, and claude.ai to query wearable health data through natural language. Runs locally over stdio, or as a remote HTTP server - see [HTTP Mode](#http-mode-remote-clients).

## Features

- **get_users**: Discover users accessible via your API key
- **get_activity_summary**: Get daily activity data (steps, calories, heart rate, intensity minutes)
- **get_sleep_summary**: Get sleep data for a user within a date range
- **get_workout_events**: Get workout/exercise sessions for a user within a date range
- **get_timeseries**: Get granular time-series samples (weight, SpO2, HRV, intraday heart rate, etc.)
- **get_menstrual_cycles**: Get menstrual cycle records (cycle day, phase, period and cycle lengths)

## Prerequisites

- [uv](https://docs.astral.sh/uv/) **>=0.9.17** package manager — upgrade with `uv self update` if needed ([docs](https://docs.astral.sh/uv/getting-started/installation/#upgrading-uv))
- Running Open Wearables backend (or access to a deployed instance)
- Valid Open Wearables API key

## Quick Start

### 1. Install dependencies

```bash
cd mcp
uv sync --group code-quality
```

### 2. Configure environment

```bash
cp config/.env.example config/.env
```

Edit `config/.env` with your settings:

```bash
OPEN_WEARABLES_API_URL=http://localhost:8000
OPEN_WEARABLES_API_KEY=ow_your_api_key_here
```

### 3. Test the server

```bash
uv run start
```

## Claude Desktop Configuration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "open-wearables": {
      "command": "uv",
      "args": [
        "run",
        "--frozen",
        "--directory",
        "/path/to/open-wearables/mcp",
        "start"
      ]
    }
  }
}
```

Replace `/path/to/open-wearables/mcp` with the actual path to this directory.

## Cursor Configuration

Add to Cursor MCP settings:

```json
{
  "mcpServers": {
    "open-wearables": {
      "command": "uv",
      "args": [
        "run",
        "--frozen",
        "--directory",
        "/path/to/open-wearables/mcp",
        "start"
      ]
    }
  }
}
```

## HTTP Mode (remote clients)

By default the server runs over stdio, launched as a local subprocess by Claude Desktop/Cursor. For remote clients (e.g. claude.ai custom connectors), run it as a standalone HTTP server instead:

```bash
MCP_TRANSPORT=http
MCP_HOST=127.0.0.1
MCP_PORT=8100
```

Bind to `127.0.0.1` and put a reverse proxy (TLS) in front - don't expose the port directly. `docker compose up -d mcp` builds and runs it as part of the main stack - transport/host/port are fixed to `http`/`0.0.0.0`/`8100` in that case (see `docker-compose.yml`), so `MCP_TRANSPORT`/`MCP_HOST`/`MCP_PORT` in `.env` only apply when running the server directly (`uv run start`).

### Authentication

HTTP mode requires one of the following (the server refuses to start without either):

- **`MCP_BEARER_TOKEN`** - a static shared secret sent as `Authorization: Bearer <token>`. Simplest option, works with clients that let you paste in a token (MCPJam, most HTTP MCP clients). Generate with `openssl rand -hex 32`.
- **`MCP_OAUTH_PASSWORD`** - a self-contained OAuth 2.1 flow (dynamic client registration + a password-gated login page). Required for clients that only support remote OAuth connectors, such as claude.ai custom connectors. Also set `MCP_PUBLIC_URL` to the server's public HTTPS URL, used for the OAuth issuer/redirect URLs. Generate the password with `openssl rand -hex 24`.

If both are set, `MCP_OAUTH_PASSWORD` takes priority.

### Connecting from claude.ai

claude.ai's custom connectors only support the OAuth flow, not a bearer token, so run the server with `MCP_OAUTH_PASSWORD` and `MCP_PUBLIC_URL` set.

1. In claude.ai, go to **Settings → Connectors → Add custom connector**.
2. Enter the server URL: `https://your-domain.example.com/mcp`.
3. claude.ai registers itself as a client and redirects you to the server's login page - enter the `MCP_OAUTH_PASSWORD` you configured. That's the only credential involved: there's no separate token to generate or copy, the OAuth exchange issues the access/refresh tokens behind the scenes.
4. Once authorized, the connector is available in your conversations.

For clients that take a manual bearer token instead (e.g. MCPJam), skip the login page entirely and paste the `MCP_BEARER_TOKEN` value as the Authorization header.

## Example Interactions

### Discovering users

```
User: "Who can I query health data for?"
Claude: [calls get_users()]
Claude: "I found 2 users: John Doe and Jane Smith."
```

### Querying sleep data

```
User: "How much sleep did John get last week?"
Claude: [calls get_users() to get John's user_id]
Claude: [calls get_sleep_summary(user_id="uuid-1", start_date="2026-01-28", end_date="2026-02-04")]
Claude: "John slept an average of 7 hours and 45 minutes over the last week.
His longest sleep was 8h 15m on Monday, and shortest was 6h 30m on Thursday."
```

### Generic request (no time range specified)

```
User: "Fetch workouts for John"
Claude: [calls get_users() to get John's user_id]
Claude: [defaults to last 2 weeks: calls get_workout_events(user_id="uuid-1", start_date="2026-01-21", end_date="2026-02-04")]
Claude: "Over the last 2 weeks, John completed 8 workouts..."
```

### Specifying time range

```
User: "Show me Jane's sleep for January 2026"
Claude: [calls get_sleep_summary(user_id="uuid-2", start_date="2026-01-01", end_date="2026-01-31")]
```

## Available Tools

### get_users

Get all users accessible via the configured API key.

**Parameters:**
- `search` (optional): Filter users by name or email

**Returns:**
```json
{
  "users": [
    {"id": "uuid-1", "first_name": "John", "last_name": "Doe", "email": "john@example.com"}
  ],
  "total": 1
}
```

### get_sleep_summary

Get sleep summaries for a user within a date range.

**Parameters:**
- `user_id` (required): UUID of the user
- `start_date` (required): Start date in YYYY-MM-DD format
- `end_date` (required): End date in YYYY-MM-DD format

**Returns:**
```json
{
  "user": {"id": "uuid-1", "first_name": "John", "last_name": "Doe"},
  "period": {"start": "2026-01-21", "end": "2026-02-04"},
  "records": [
    {
      "date": "2026-02-03",
      "start_datetime": "2026-02-03T23:15:00+00:00",
      "end_datetime": "2026-02-04T07:30:00+00:00",
      "duration_minutes": 495,
      "source": "whoop"
    }
  ],
  "summary": {
    "total_nights": 7,
    "nights_with_data": 6,
    "avg_duration_minutes": 465,
    "min_duration_minutes": 360,
    "max_duration_minutes": 540
  }
}
```

## Architecture

```
mcp/
├── app/
│   ├── main.py           # FastMCP entry point
│   ├── config.py         # Settings (API URL, API key, transport, auth)
│   ├── auth.py           # Bearer token verifier (HTTP mode)
│   ├── oauth.py          # OAuth 2.1 provider (HTTP mode)
│   ├── tools/
│   │   ├── users.py      # get_users tool
│   │   ├── activity.py   # get_activity_summary tool
│   │   ├── sleep.py      # get_sleep_summary tool
│   │   ├── workouts.py   # get_workout_events tool
│   │   ├── timeseries.py # get_timeseries tool
│   │   └── menstrual_cycles.py # get_menstrual_cycles tool
│   └── services/
│       └── api_client.py # HTTP client for backend API
├── config/
│   └── .env.example      # Environment template
├── pyproject.toml
└── README.md
```

The MCP server is **decoupled** from the backend - it communicates via REST API using your API key. This means:
- No shared database access
- Can be deployed independently
- Uses existing, tested API endpoints

## Development

### Running locally

```bash
# Start the backend first (from project root)
docker compose up -d

# Then start the MCP server
cd mcp
uv run start
```

### Testing with MCPJam

[MCPJam](https://www.mcpjam.com/) is a local inspector for testing MCP servers. It provides a UI to explore tools, test calls, and debug responses.

```bash
npx @mcpjam/inspector@latest
```

Then configure the connection:
- **Command**: `uv`
- **Arguments**: `run --frozen --directory /path/to/open-wearables/mcp start`

### Code quality

```bash
uv run pre-commit run --all-files
```

## Troubleshooting

### "Invalid API key" error

Ensure your `OPEN_WEARABLES_API_KEY` in `config/.env` is valid. You can get an API key from:
1. The Open Wearables developer portal
2. Or via the backend admin panel at `/api/v1/developer/api-keys`

### "Connection refused" error

Make sure the backend is running at the URL specified in `OPEN_WEARABLES_API_URL`.

For local development:
```bash
# From project root
docker compose up -d
```

### No users found

The API key determines which users you can see. Ensure:
1. Users have been created via the API or SDK
2. Your API key has access to those users

## License

MIT - See the main project LICENSE file.

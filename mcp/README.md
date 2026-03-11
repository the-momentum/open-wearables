# Open Wearables MCP Server

MCP (Model Context Protocol) server for Open Wearables, enabling AI assistants like Claude Desktop and Cursor to query wearable health data through natural language.

## Features

- **get_users**: Discover users accessible via your API key
- **get_activity_summary**: Get daily activity data (steps, calories, heart rate, intensity minutes)
- **get_sleep_summary**: Get sleep data for a user within a date range
- **get_workout_events**: Get workout/exercise sessions for a user within a date range

## Prerequisites

- [uv](https://docs.astral.sh/uv/) package manager
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
      "duration_formatted": "8h 15m",
      "source": "whoop"
    }
  ],
  "summary": {
    "total_nights": 7,
    "nights_with_data": 6,
    "avg_duration_minutes": 465,
    "avg_duration_formatted": "7h 45m",
    "min_duration_minutes": 360,
    "max_duration_minutes": 540
  }
}
```

## Transports

The server supports two transport protocols, selected via the `MCP_TRANSPORT` environment variable.

### stdio (default)

For local AI assistants (Claude Desktop, Cursor). This is the default - no extra config needed.

```bash
uv run start
```

### HTTP (Streamable HTTP)

For remote deployment (Railway, cloud VMs, etc.). Uses the MCP Streamable HTTP protocol.

```bash
MCP_TRANSPORT=http uv run start
```

The server listens on `http://0.0.0.0:8080/mcp` by default. Customize with `MCP_HOST` and `MCP_PORT`.

#### Authentication (OAuth 2.1)

The server implements the full MCP authorization spec (OAuth 2.1 with Dynamic Client Registration). When a user connects via Claude Desktop or another MCP client:

1. The client discovers OAuth endpoints at `/.well-known/oauth-authorization-server`
2. The client registers via Dynamic Client Registration (`POST /register`)
3. The user is redirected to an API key entry form
4. The user enters their Open Wearables API key from the developer panel
5. The server validates the key against the backend
6. An OAuth access token is issued - the API key is embedded in the token claims

Each user's API key determines which data they can access - the same scoping as the REST API. The `/health` endpoint is always unauthenticated.

#### Connecting via Claude Desktop

In Claude Desktop, go to **Settings > Connectors > Add custom connector** and enter:

```
https://your-deployment.railway.app/mcp
```

Claude will handle the OAuth flow automatically - the user just needs to enter their API key when prompted.

## Deploy to Railway

### 1. Create a new Railway service

Point it at the `mcp/` directory of this repo (or use the included `Dockerfile` and `railway.toml`).

### 2. Set environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPEN_WEARABLES_API_URL` | Yes | Backend API URL (e.g. `https://api.your-domain.com`) |
| `MCP_TRANSPORT` | Yes | Set to `http` |
| `MCP_BASE_URL` | Yes | Public URL of this server (e.g. `https://mcp.railway.app`) |

`OPEN_WEARABLES_API_KEY` is **not needed** in HTTP mode - each user authenticates with their own API key via the OAuth flow. Railway automatically injects `PORT`.

### 3. Health check

Railway uses `/health` for health checks (configured in `railway.toml`).

## Architecture

```
mcp/
├── app/
│   ├── main.py           # FastMCP entry point (stdio + HTTP)
│   ├── config.py         # Settings (API URL, API key, transport)
│   ├── auth.py           # Bearer token auth for HTTP transport
│   ├── tools/
│   │   ├── users.py      # get_users tool
│   │   ├── activity.py   # get_activity_summary tool
│   │   ├── sleep.py      # get_sleep_summary tool
│   │   └── workouts.py   # get_workout_events tool
│   └── services/
│       └── api_client.py # HTTP client for backend API
├── config/
│   └── .env.example      # Environment template
├── Dockerfile            # Container image for Railway
├── railway.toml          # Railway deployment config
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

### Testing HTTP transport locally

```bash
# Start in HTTP mode
MCP_TRANSPORT=http MCP_PORT=9000 MCP_BASE_URL=http://localhost:9000 uv run start

# Test health
curl http://localhost:9000/health

# Test OAuth discovery
curl http://localhost:9000/.well-known/oauth-authorization-server

# Register a client (DCR)
curl -X POST http://localhost:9000/register \
  -H "Content-Type: application/json" \
  -d '{"client_name":"test","redirect_uris":["http://localhost:3000/callback"],"grant_types":["authorization_code"],"response_types":["code"],"token_endpoint_auth_method":"none"}'
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

### 401 Unauthorized on MCP endpoint

In HTTP mode, all MCP requests require a valid OAuth access token obtained through the OAuth 2.1 flow. If you're using Claude Desktop, reconnect via Settings > Connectors. The `/health` endpoint does not require auth.

### No users found

The API key determines which users you can see. Ensure:
1. Users have been created via the API or SDK
2. Your API key has access to those users

## License

MIT - See the main project LICENSE file.

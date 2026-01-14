# Open Wearables MCP Server

MCP (Model Context Protocol) server for Open Wearables, enabling AI assistants like Claude Desktop and Cursor to query wearable health data through natural language.

## Features

- **list_users**: Discover users accessible via your API key
- **get_sleep_records**: Get sleep data for a user over the last X days
- **get_workouts**: Get workout data for a user over the last X days

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Running Open Wearables backend (or access to a deployed instance)
- Valid Open Wearables API key

## Quick Start

### 1. Install dependencies

```bash
cd mcp
uv sync
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
Claude: [calls list_users()]
Claude: "I found 2 users: John Doe and Jane Smith."
```

### Querying sleep data

```
User: "How much sleep did John get this week?"
Claude: [calls get_sleep_records(user_name="John", days=7)]
Claude: "John slept an average of 7 hours and 45 minutes over the last week.
His longest sleep was 8h 15m on Monday, and shortest was 6h 30m on Thursday."
```

### Specifying time range

```
User: "Show me Jane's sleep for the last month"
Claude: [calls get_sleep_records(user_name="Jane", days=30)]
```

### Querying workout data

```
User: "What workouts did John do this week?"
Claude: [calls get_workouts(user_name="John", days=7)]
Claude: "John completed 5 workouts this week: 3 runs and 2 cycling sessions.
Total distance: 45 km. Total duration: 3h 28m."
```

### Filtering by workout type

```
User: "Show me all of Jane's runs in the last 2 weeks"
Claude: [calls get_workouts(user_name="Jane", days=14, workout_type="running")]
```

## Available Tools

### list_users

List all users accessible via the configured API key.

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

### get_sleep_records

Get sleep records for a user over the last X days.

**Parameters:**
- `user_id` (optional): UUID of the user
- `user_name` (optional): First name to search for
- `days` (optional): Number of days to look back (default: 7, max: 90)

**Returns:**
```json
{
  "user": {"id": "uuid-1", "first_name": "John", "last_name": "Doe"},
  "period": {"start": "2025-01-05", "end": "2025-01-12"},
  "records": [
    {
      "date": "2025-01-11",
      "start_time": "23:15",
      "end_time": "07:30",
      "duration_minutes": 495,
      "duration_formatted": "8h 15m",
      "source": "whoop"
    }
  ],
  "summary": {
    "total_nights": 7,
    "nights_with_data": 6,
    "avg_duration_minutes": 465,
    "avg_duration_formatted": "7h 45m"
  }
}
```

### get_workouts

Get workout records for a user over the last X days.

**Parameters:**
- `user_id` (optional): UUID of the user
- `user_name` (optional): First name to search for
- `days` (optional): Number of days to look back (default: 7, max: 90)
- `workout_type` (optional): Filter by type (e.g., "running", "cycling", "swimming")

**Returns:**
```json
{
  "user": {"id": "uuid-1", "first_name": "John", "last_name": "Doe"},
  "period": {"start": "2025-01-07", "end": "2025-01-14"},
  "workouts": [
    {
      "date": "2025-01-13",
      "type": "running",
      "name": "Morning Run",
      "start_time": "07:15",
      "end_time": "08:02",
      "duration_seconds": 2820,
      "duration_formatted": "47m",
      "distance_meters": 7500,
      "distance_formatted": "7.50 km",
      "calories_kcal": 520,
      "avg_heart_rate_bpm": 145,
      "max_heart_rate_bpm": 172,
      "pace_formatted": "6:16 min/km",
      "elevation_gain_meters": 85,
      "source": "garmin"
    }
  ],
  "summary": {
    "total_workouts": 5,
    "workouts_by_type": {"running": 3, "cycling": 2},
    "total_duration_seconds": 12500,
    "total_duration_formatted": "3h 28m",
    "total_distance_meters": 45000,
    "total_distance_formatted": "45.00 km",
    "total_calories_kcal": 2100
  }
}
```

## Architecture

```
mcp/
├── app/
│   ├── main.py           # FastMCP entry point
│   ├── config.py         # Settings (API URL, API key)
│   ├── tools/
│   │   ├── users.py      # list_users tool
│   │   ├── sleep.py      # get_sleep_records tool
│   │   └── workouts.py   # get_workouts tool
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

### Code quality

```bash
uv run ruff check . --fix
uv run ruff format .
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

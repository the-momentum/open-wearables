# Open Wearables Python SDK

> [!CAUTION]
> This is SDK is unstable beta right now.

A typed, async-ready Python SDK for the [Open Wearables API](https://github.com/TudorGR/open-wearables).

## Installation

```bash
pip install open-wearables
```

## Quick Start

```python
from open_wearables import OpenWearables

# Initialize the client
client = OpenWearables(api_key="ow_your_api_key")

# Create a user
user = client.users.create(
    external_user_id="user_123",
    email="john@example.com"
)

# Fetch workouts
workouts = client.users.get_workouts(
    user_id=user.id,
    start_date="2025-01-01",
    limit=50
)

for workout in workouts:
    print(f"{workout.type}: {workout.duration_seconds}s")

# Get user connections
connections = client.users.get_connections(user_id=user.id)

# Get heart rate data
heart_rate = client.users.get_heart_rate(user_id=user.id)
```

## Async Usage

All methods have async variants prefixed with `a`:

```python
import asyncio
from open_wearables import OpenWearables

async def main():
    async with OpenWearables(api_key="ow_your_api_key") as client:
        # Create a user
        user = await client.users.acreate(
            external_user_id="user_123",
            email="john@example.com"
        )

        # Fetch workouts
        workouts = await client.users.aget_workouts(
            user_id=user.id,
            start_date="2025-01-01",
            limit=50
        )

        for workout in workouts:
            print(f"{workout.type}: {workout.duration_seconds}s")

asyncio.run(main())
```

## Configuration

```python
from open_wearables import OpenWearables

client = OpenWearables(
    api_key="ow_your_api_key",
    base_url="https://api.openwearables.io",  # Optional: custom base URL
    timeout=30.0,  # Optional: request timeout in seconds
)
```

## API Reference

### Users

```python
# List all users
users = client.users.list()

# Get a user by ID
user = client.users.get(user_id="uuid")

# Create a user
user = client.users.create(
    external_user_id="your_user_id",
    email="user@example.com",
    first_name="John",
    last_name="Doe",
)

# Update a user
user = client.users.update(
    user_id="uuid",
    email="new@example.com",
)

# Delete a user
user = client.users.delete(user_id="uuid")
```

### Workouts

```python
# Get workouts for a user
workouts = client.users.get_workouts(
    user_id="uuid",
    start_date="2025-01-01T00:00:00Z",
    end_date="2025-12-31T23:59:59Z",
    workout_type="HKWorkoutActivityTypeRunning",
    source_name="Apple Watch",
    min_duration=300,  # 5 minutes
    max_duration=7200,  # 2 hours
    limit=50,
    offset=0,
    sort_by="start_datetime",
    sort_order="desc",
)
```

### Connections

```python
# Get user connections to fitness providers
connections = client.users.get_connections(user_id="uuid")
```

### Heart Rate

```python
# Get heart rate data
heart_rate = client.users.get_heart_rate(user_id="uuid")
```

## Error Handling

```python
from open_wearables import OpenWearables
from open_wearables.exceptions import (
    AuthenticationError,
    NotFoundError,
    ValidationError,
    RateLimitError,
    ServerError,
)

client = OpenWearables(api_key="ow_your_api_key")

try:
    user = client.users.get(user_id="non-existent-id")
except NotFoundError:
    print("User not found")
except AuthenticationError:
    print("Invalid API key")
except ValidationError as e:
    print(f"Validation error: {e.response}")
except RateLimitError:
    print("Rate limit exceeded, try again later")
except ServerError:
    print("Server error, try again later")
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy src

# Linting
ruff check src
```

## License

MIT License - see [LICENSE](../../LICENSE) for details.

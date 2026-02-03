"""Open Wearables MCP Server - Main entry point."""

import logging

from fastmcp import FastMCP

from app.config import settings
from app.tools.sleep import sleep_router
from app.tools.users import users_router
from app.tools.workouts import workouts_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

# Create FastMCP server instance
mcp = FastMCP(
    "open-wearables",
    instructions="""
    Enables the model to query data describing user health states and general wellness metrics.
    Data is acquired from users' wearable devices (Garmin, Whoop, Polar, Suunto, etc.),
    covering all user-connected devices and providers, aggregated into a single unified format.

    Available tools:
    - list_users: Discover users accessible via your API key
    - list_sleep: Get sleep data for a user over a specified time period
    - list_workouts: Get workout/exercise data for a user over a specified time period

    Workflow:
    1. If you don't know the user's ID, call list_users first to discover available users
    2. Select the appropriate user:
       - If only ONE user is returned: use that user automatically (personal API key)
       - If MULTIPLE users and query says "my" or "me": ask which user they mean
       - If MULTIPLE users with a name hint (e.g., "John's workouts"): match by name
    3. Use the user's ID to query their health data with the appropriate tool
    4. Present the data in a human-friendly format, highlighting key insights

    Example interaction:
    User: "How did I sleep last week?"
    Assistant actions:
      1. Call list_users() to find the user's ID
      2. Calculate dates: start_date = 7 days ago, end_date = today
      3. Call list_sleep(user_id="{user_id}", start_date="2025-01-13", end_date="2025-01-20")
      4. Respond with: "Over the past week, you averaged 7.2 hours of sleep per night.
         Your best night was Tuesday (8.1 hours), and your shortest was Friday (5.9 hours).
         Your sleep efficiency averaged 89%, which is good."

    Example interaction:
    User: "Compare my sleep this week vs last week"
    Assistant actions:
      1. Calculate dates for two-week period: start_date = 14 days ago, end_date = today
      2. Call list_sleep(user_id="{user_id}", start_date="2025-01-06", end_date="2025-01-20")
      3. Analyze the data, splitting into two 7-day periods
      4. Respond with a comparison highlighting trends and changes

    Example interaction:
    User: "Show me my workouts this week"
    Assistant actions:
      1. Call list_users() to find the user's ID
      2. Calculate dates: start_date = 7 days ago, end_date = today
      3. Call list_workouts(user_id="{user_id}", start_date="2025-01-13", end_date="2025-01-20")
      4. Respond with: "This week you completed 5 workouts totaling 3.5 hours.
         You ran 28.5 km across 3 running sessions and did 2 strength workouts.
         Your total calories burned was 2,100 kcal."

    Example interaction:
    User: "How many miles did I run last month?"
    Assistant actions:
      1. Calculate dates for last month: start_date = first of last month, end_date = last of last month
      2. Call list_workouts(user_id="{user_id}", start_date="2024-12-01", end_date="2024-12-31", workout_type="running")
      3. Convert distance from km to miles and respond with the total

    The API key determines which users you can access (personal, team, or enterprise scope).
    All data is returned in a normalized format regardless of the original wearable provider.
    """,
)

# Mount tool routers
mcp.mount(users_router)
mcp.mount(sleep_router)
mcp.mount(workouts_router)

logger.info(f"Open Wearables MCP server initialized. API URL: {settings.open_wearables_api_url}")


def main() -> None:
    """Entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()

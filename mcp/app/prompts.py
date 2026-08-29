"""MCP prompts for guiding LLM interactions with health data."""

from fastmcp import FastMCP
from fastmcp.prompts import Message

# Create router for prompts
prompts_router = FastMCP(name="Health Data Prompts")


@prompts_router.prompt
def present_health_data() -> list[Message]:
    """Guidelines for presenting health data to users in a readable format."""
    return [
        Message(
            role="user",
            content="""When presenting health data to users, follow these formatting guidelines:

**Numbers and Units:**
- Steps: format for readability (e.g., 8432 steps)
- Distance: convert meters to km, round to 2 decimal places (e.g., 6240.5m → 6.24 km)
- Calories: round to whole numbers (e.g., 2150 kcal)
- Duration in minutes: convert to hours/minutes if >= 60 (e.g., 75 min → 1h 15m)
- Heart rate: always include "bpm" unit (e.g., 72 bpm)
- Percentages: round to 1 decimal place (e.g., 89.5%)

**Presentation Style:**
- Lead with insights, not raw numbers
- Highlight notable patterns (best/worst days, trends)
- Compare to goals or typical ranges when relevant
- Use natural language, not data dumps
- Group related metrics together

**Example Good Response:**
"This week you averaged 8400 steps per day, totaling 58800 steps. Your most active
day was Saturday (12400 steps), while Wednesday was your lowest (5200 steps).
You burned 2450 active calories and spent 90 minutes in vigorous activity zones."

**Example Bad Response:**
"steps: 58800, distance_meters: 43680.5, active_calories_kcal: 2450.3,
total_calories_kcal: 15050.0, avg_active_minutes: 55"
""",
        )
    ]

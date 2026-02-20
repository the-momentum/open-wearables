"""Shared configuration constants for Garmin backfill.

Used by both the backfill service (handlers/backfill.py) and the
Celery task orchestrator (garmin_backfill_task.py).
"""

# ---------------------------------------------------------------------------
# Redis tracking
# ---------------------------------------------------------------------------
REDIS_PREFIX = "garmin:backfill"
REDIS_TTL = 86400 * 7  # 7 days TTL for backfill tracking

# ---------------------------------------------------------------------------
# Garmin rate limits
# ---------------------------------------------------------------------------
GARMIN_RATE_LIMIT_WINDOW = 60  # seconds
GARMIN_RATE_LIMIT_REQUESTS = 100
GARMIN_BACKFILL_BUDGET_PCT = 0.3  # Reserve 30% of rate limit for backfill

# Rate limiting delays (derived from Garmin's 100 req/min limit)
_backfill_budget = int(GARMIN_RATE_LIMIT_REQUESTS * GARMIN_BACKFILL_BUDGET_PCT)  # 30 req/min
DELAY_BETWEEN_TYPES = GARMIN_RATE_LIMIT_WINDOW // _backfill_budget  # 2s between types
DELAY_AFTER_RATE_LIMIT = GARMIN_RATE_LIMIT_WINDOW  # Wait for full window reset (60s)

# ---------------------------------------------------------------------------
# Timeout / retry
# ---------------------------------------------------------------------------
TRIGGERED_TIMEOUT_SECONDS = 300  # 5 min before skipping a triggered type
MAX_TYPE_ATTEMPTS = 3  # Total attempts (1 original + 2 retries) -- legacy, unused in task

# ---------------------------------------------------------------------------
# Concurrency lock
# ---------------------------------------------------------------------------
# 12 windows * 5 types * 5min timeout + 1hr buffer = ~7 hours safety net for crash recovery
BACKFILL_LOCK_TTL = (12 * 5 * 300) + 3600  # 21600 seconds (6 hours)

# ---------------------------------------------------------------------------
# Backfill windows & API limits
# ---------------------------------------------------------------------------
MAX_BACKFILL_DAYS = 365  # Total target: ~1 year of history
BACKFILL_CHUNK_DAYS = 30  # Max days per single request (Garmin limit)
MAX_REQUEST_DAYS = BACKFILL_CHUNK_DAYS  # Alias for clarity
MAX_HEALTH_API_DAYS = 30  # Health API max days per request
MAX_ACTIVITY_API_DAYS = 30  # Activity API max days per request
BACKFILL_WINDOW_COUNT = 12  # Number of 30-day windows to cover ~365 days
DEFAULT_BACKFILL_DAYS = 1  # Default for subsequent syncs

# ---------------------------------------------------------------------------
# Recovery / GC
# ---------------------------------------------------------------------------
GC_MAX_ATTEMPTS = 3  # Max GC-and-retry cycles before permanently failed
GC_STUCK_THRESHOLD_SECONDS = 600  # 10 minutes of no activity = stuck
GC_SCAN_INTERVAL_SECONDS = 180  # Every 3 minutes (used by celery beat in Plan 02)
SUMMARY_DAYS = 0  # No summary coverage gap (REST endpoints removed)
REQUEST_DELAY_SECONDS = 0.5  # Small delay between requests (prod limit: 10,000 days/min)


def get_max_days_for_type(data_type: str) -> int:
    """Get maximum backfill days allowed for a data type.

    All data types are currently limited to 30 days per request.
    """
    return BACKFILL_CHUNK_DAYS


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

# Data types that use the Activity API (same 30-day limit as all types)
ACTIVITY_API_TYPES = {"activities", "activityDetails"}

# All 16 data types to backfill
ALL_DATA_TYPES = [
    "sleeps",
    "dailies",
    "epochs",
    "bodyComps",
    "hrv",
    "activities",
    "activityDetails",
    "moveiq",
    "healthSnapshot",
    "stressDetails",
    "respiration",
    "pulseOx",
    "bloodPressures",
    "userMetrics",
    "skinTemp",
    "mct",
]

# Data types included in backfill orchestration (subset of ALL_DATA_TYPES).
# All 16 types remain available for webhook ingestion.
BACKFILL_DATA_TYPES = [
    "sleeps",
    "dailies",
    "activities",
    "activityDetails",
    "hrv",
]

# Mapping of data type to backfill endpoint
BACKFILL_ENDPOINTS = {
    "sleeps": "/wellness-api/rest/backfill/sleeps",
    "dailies": "/wellness-api/rest/backfill/dailies",
    "epochs": "/wellness-api/rest/backfill/epochs",
    "bodyComps": "/wellness-api/rest/backfill/bodyComps",
    "hrv": "/wellness-api/rest/backfill/hrv",
    "stressDetails": "/wellness-api/rest/backfill/stressDetails",
    "respiration": "/wellness-api/rest/backfill/respiration",
    "pulseOx": "/wellness-api/rest/backfill/pulseOx",
    "activities": "/wellness-api/rest/backfill/activities",
    "activityDetails": "/wellness-api/rest/backfill/activityDetails",
    "userMetrics": "/wellness-api/rest/backfill/userMetrics",
    "bloodPressures": "/wellness-api/rest/backfill/bloodPressures",
    "skinTemp": "/wellness-api/rest/backfill/skinTemp",
    "healthSnapshot": "/wellness-api/rest/backfill/healthSnapshot",
    "moveiq": "/wellness-api/rest/backfill/moveiq",
    "mct": "/wellness-api/rest/backfill/mct",
}

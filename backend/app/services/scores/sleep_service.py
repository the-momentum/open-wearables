"""Sleep score service.

Translates raw overnight sleep sessions into per-night OW sleep scores using
the four-pillar algorithm (duration 40%, stages 20%, consistency 20%,
interruptions 20%).

Processing pipeline (mirrors sleep_analysis.ipynb):
  1. Filter out naps.
  2. Deduplicate to one session per night (wake-up date convention; keep longest).
  3. Sort chronologically.
  4. For each night: build rolling 14-night bedtime history, parse stage blocks
     for true WASO, compute net sleep, and score via calculate_overall_sleep_score.
"""

from datetime import date, datetime

from pydantic import BaseModel

from app.algorithms.config_algorithms import sleep_consistency_config
from app.algorithms.sleep import (
    calculate_overall_sleep_score,
    convert_stages_to_duration_blocks,
    parse_wearable_stages_for_interruptions,
)

_DATETIME_FMT = "%Y-%m-%dT%H:%M:%S"


class SleepSession(BaseModel):
    """A single sleep session as stored in EventRecord + SleepDetails."""

    sleep_event_id: str
    start_datetime: datetime
    end_datetime: datetime
    is_nap: bool = False
    sleep_total_duration_minutes: float | None = None
    sleep_deep_minutes: float | None = None
    sleep_rem_minutes: float | None = None
    sleep_awake_minutes: float | None = None
    # Raw stage blocks: [{"stage": "...", "start_time": "...", "end_time": "..."}, ...]
    # When present, used to derive true WASO (strips sleep latency & morning lie-in).
    # When absent, sleep_awake_minutes is used as a fallback.
    sleep_stages: list[dict[str, str]] | None = None


class SleepScoreRecord(BaseModel):
    """Scored result for a single overnight sleep session."""

    sleep_event_id: str
    sleep_date: date
    overall_score: int
    duration_score: int
    stages_score: int
    consistency_score: int
    interruptions_score: int
    duration_hours: float
    net_sleep_minutes: float


def score_sleep_sessions(sessions: list[SleepSession]) -> list[SleepScoreRecord]:
    """Score overnight sleep sessions for a single user.

    Args:
        sessions: All sleep sessions for a user (any order, may include naps).

    Returns:
        One SleepScoreRecord per night, sorted chronologically.
    """
    overnight = [s for s in sessions if not s.is_nap]
    if not overnight:
        return []

    # One session per night: use wake-up date (end_datetime) as the sleep date.
    # When multiple sessions share a date, keep the longest.
    by_date: dict[date, SleepSession] = {}
    for s in overnight:
        d = s.end_datetime.date()
        if d not in by_date or (s.sleep_total_duration_minutes or 0) > (
            by_date[d].sleep_total_duration_minutes or 0
        ):
            by_date[d] = s

    daily = sorted(by_date.values(), key=lambda s: s.end_datetime.date())

    results: list[SleepScoreRecord] = []
    for i, session in enumerate(daily):
        # Rolling bedtime history (up to ROLLING_WINDOW prior nights).
        # Night 0 has no history → consistency defaults to 100 (base score).
        history_start = max(0, i - sleep_consistency_config.rolling_window_nights)
        historical_bedtimes = [
            daily[j].start_datetime.strftime(_DATETIME_FMT)
            for j in range(history_start, i)
        ]

        # Parse per-stage blocks for true WASO; fall back to aggregated awake minutes.
        if session.sleep_stages:
            duration_blocks = convert_stages_to_duration_blocks(session.sleep_stages)
            interruption_data = parse_wearable_stages_for_interruptions(duration_blocks)
            total_awake: float = interruption_data["total_awake_minutes"]
            awakenings: list[float] = interruption_data["awakening_durations"]
        else:
            total_awake = session.sleep_awake_minutes or 0.0
            awakenings = []

        # Net sleep: sleep_total_duration_minutes is canonical; timestamps are display-only.
        net_sleep_minutes = max(
            0.0,
            (session.sleep_total_duration_minutes or 0.0)
            - (session.sleep_awake_minutes or 0.0),
        )

        scored = calculate_overall_sleep_score(
            total_sleep_minutes=net_sleep_minutes,
            deep_minutes=session.sleep_deep_minutes or 0.0,
            rem_minutes=session.sleep_rem_minutes or 0.0,
            session_start=session.start_datetime.strftime(_DATETIME_FMT),
            historical_bedtimes=historical_bedtimes,
            total_awake_minutes=total_awake,
            awakening_durations=awakenings,
        )

        results.append(
            SleepScoreRecord(
                sleep_event_id=session.sleep_event_id,
                sleep_date=session.end_datetime.date(),
                overall_score=scored["overall_score"],
                duration_score=scored["breakdown"]["duration"]["score"],
                stages_score=scored["breakdown"]["stages"]["score"],
                consistency_score=scored["breakdown"]["consistency"]["score"],
                interruptions_score=scored["breakdown"]["interruptions"]["score"],
                duration_hours=scored["metrics"]["duration_hours"],
                net_sleep_minutes=net_sleep_minutes,
            )
        )

    return results

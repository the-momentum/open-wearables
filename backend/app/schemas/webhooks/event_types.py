"""Webhook event types emitted by Open Wearables.

Each value follows the Svix convention: ``<resource>.<action>``.
Keep in sync with the init script that registers them with the Svix server.

Discrete EventRecord events (workout, sleep, activity) are distinct from
TimeSeries events: the former represent complete sessions, the latter are
batched samples (HR, steps, etc.) ingested from a provider.
"""

from enum import StrEnum


class WebhookEventType(StrEnum):
    # EventRecord-based (discrete sessions)
    WORKOUT_CREATED = "workout.created"
    SLEEP_CREATED = "sleep.created"
    ACTIVITY_CREATED = "activity.created"

    # TimeSeries-based (batched samples per ingestion)
    HEART_RATE_UPDATED = "heart_rate.updated"
    HEART_RATE_VARIABILITY_UPDATED = "heart_rate_variability.updated"
    STEPS_UPDATED = "steps.updated"
    CALORIES_UPDATED = "calories.updated"
    SPO2_UPDATED = "spo2.updated"
    RESPIRATORY_RATE_UPDATED = "respiratory_rate.updated"
    BODY_TEMPERATURE_UPDATED = "body_temperature.updated"
    STRESS_UPDATED = "stress.updated"
    BLOOD_GLUCOSE_UPDATED = "blood_glucose.updated"
    BLOOD_PRESSURE_UPDATED = "blood_pressure.updated"

    # Catch-all for series types not yet mapped explicitly
    TIMESERIES_UPDATED = "timeseries.updated"


# Human-readable descriptions shown in the Svix dashboard and event-types endpoint
EVENT_TYPE_DESCRIPTIONS: dict[WebhookEventType, str] = {
    WebhookEventType.WORKOUT_CREATED: "A new workout session was saved.",
    WebhookEventType.SLEEP_CREATED: "A new (or merged) sleep session was saved.",
    WebhookEventType.ACTIVITY_CREATED: "A new generic activity session was saved.",
    WebhookEventType.HEART_RATE_UPDATED: "New heart-rate samples were ingested.",
    WebhookEventType.HEART_RATE_VARIABILITY_UPDATED: "New HRV samples were ingested.",
    WebhookEventType.STEPS_UPDATED: "New step samples were ingested.",
    WebhookEventType.CALORIES_UPDATED: "New calorie/energy samples were ingested.",
    WebhookEventType.SPO2_UPDATED: "New SpO2 samples were ingested.",
    WebhookEventType.RESPIRATORY_RATE_UPDATED: "New respiratory-rate samples were ingested.",
    WebhookEventType.BODY_TEMPERATURE_UPDATED: "New body temperature samples were ingested.",
    WebhookEventType.STRESS_UPDATED: "New stress-level samples were ingested.",
    WebhookEventType.BLOOD_GLUCOSE_UPDATED: "New blood-glucose samples were ingested.",
    WebhookEventType.BLOOD_PRESSURE_UPDATED: "New blood-pressure samples were ingested.",
    WebhookEventType.TIMESERIES_UPDATED: "New time-series samples of an unspecified type were ingested.",
}

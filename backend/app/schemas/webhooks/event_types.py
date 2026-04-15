"""Webhook event types emitted by Open Wearables.

Each value follows the Svix convention: ``<resource>.<action>``.
Keep in sync with the init script that registers them with the Svix server.

All events use the ``created`` action — there is no update/patch flow.
Discrete EventRecord events (workout, sleep, activity) represent complete
sessions; TimeSeries events represent batched samples (HR, steps, etc.)
received from a provider during an ingestion run.
"""

from enum import StrEnum


class WebhookEventType(StrEnum):
    # Provider connection events
    CONNECTION_CREATED = "connection.created"

    # EventRecord-based (discrete sessions)
    WORKOUT_CREATED = "workout.created"
    SLEEP_CREATED = "sleep.created"
    ACTIVITY_CREATED = "activity.created"

    # TimeSeries-based (batched samples per ingestion)
    HEART_RATE_CREATED = "heart_rate.created"
    HEART_RATE_VARIABILITY_CREATED = "heart_rate_variability.created"
    STEPS_CREATED = "steps.created"
    CALORIES_CREATED = "calories.created"
    SPO2_CREATED = "spo2.created"
    RESPIRATORY_RATE_CREATED = "respiratory_rate.created"
    BODY_TEMPERATURE_CREATED = "body_temperature.created"
    STRESS_CREATED = "stress.created"
    BLOOD_GLUCOSE_CREATED = "blood_glucose.created"
    BLOOD_PRESSURE_CREATED = "blood_pressure.created"
    BODY_COMPOSITION_CREATED = "body_composition.created"
    FITNESS_METRICS_CREATED = "fitness_metrics.created"
    RECOVERY_SCORE_CREATED = "recovery_score.created"
    ACTIVITY_CREATED_TIMESERIES = "activity_timeseries.created"
    WORKOUT_METRICS_CREATED = "workout_metrics.created"
    ENVIRONMENTAL_CREATED = "environmental.created"

    # Catch-all for series types not yet mapped explicitly
    TIMESERIES_CREATED = "timeseries.created"


# Human-readable descriptions shown in the Svix dashboard and event-types endpoint
EVENT_TYPE_DESCRIPTIONS: dict[WebhookEventType, str] = {
    WebhookEventType.CONNECTION_CREATED: "A user successfully connected a wearable provider.",
    WebhookEventType.WORKOUT_CREATED: "A new workout session was saved.",
    WebhookEventType.SLEEP_CREATED: "A new (or merged) sleep session was saved.",
    WebhookEventType.ACTIVITY_CREATED: "A new generic activity session was saved.",
    WebhookEventType.HEART_RATE_CREATED: "New heart-rate samples were ingested.",
    WebhookEventType.HEART_RATE_VARIABILITY_CREATED: "New HRV samples were ingested.",
    WebhookEventType.STEPS_CREATED: "New step samples were ingested.",
    WebhookEventType.CALORIES_CREATED: "New calorie/energy samples were ingested.",
    WebhookEventType.SPO2_CREATED: "New SpO2 samples were ingested.",
    WebhookEventType.RESPIRATORY_RATE_CREATED: "New respiratory-rate samples were ingested.",
    WebhookEventType.BODY_TEMPERATURE_CREATED: "New body-temperature samples were ingested.",
    WebhookEventType.STRESS_CREATED: "New stress-level samples were ingested.",
    WebhookEventType.BLOOD_GLUCOSE_CREATED: "New blood-glucose samples were ingested.",
    WebhookEventType.BLOOD_PRESSURE_CREATED: "New blood-pressure samples were ingested.",
    WebhookEventType.BODY_COMPOSITION_CREATED: (
        "New body-composition samples (weight, BMI, body fat, etc.) were ingested."
    ),
    WebhookEventType.FITNESS_METRICS_CREATED: (
        "New fitness-metrics samples (VO2max, cardiovascular age, etc.) were ingested."
    ),
    WebhookEventType.RECOVERY_SCORE_CREATED: "New recovery-score samples were ingested.",
    WebhookEventType.ACTIVITY_CREATED_TIMESERIES: (
        "New activity samples (distance, stand time, exercise time, etc.) were ingested."
    ),
    WebhookEventType.WORKOUT_METRICS_CREATED: (
        "New workout-metrics samples (cadence, power, running/walking/swimming metrics, etc.) were ingested."
    ),
    WebhookEventType.ENVIRONMENTAL_CREATED: (
        "New environmental samples (audio exposure, UV, weather, etc.) were ingested."
    ),
    WebhookEventType.TIMESERIES_CREATED: "New time-series samples of an unspecified type were ingested.",
}

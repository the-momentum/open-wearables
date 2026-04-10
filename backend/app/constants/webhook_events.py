"""Maps SeriesType slugs to their outgoing webhook event type.

Used by the timeseries emit helper to select the most specific event type
for a given measurement kind. Falls back to ``WebhookEventType.TIMESERIES_UPDATED``
when the series type is not listed here.
"""

from app.schemas.webhooks.event_types import WebhookEventType

SERIES_TYPE_TO_WEBHOOK_EVENT: dict[str, str] = {
    "heart_rate": WebhookEventType.HEART_RATE_UPDATED,
    "resting_heart_rate": WebhookEventType.HEART_RATE_UPDATED,
    "heart_rate_variability_sdnn": WebhookEventType.HEART_RATE_VARIABILITY_UPDATED,
    "heart_rate_variability_rmssd": WebhookEventType.HEART_RATE_VARIABILITY_UPDATED,
    "steps": WebhookEventType.STEPS_UPDATED,
    "energy": WebhookEventType.CALORIES_UPDATED,
    "basal_energy": WebhookEventType.CALORIES_UPDATED,
    "oxygen_saturation": WebhookEventType.SPO2_UPDATED,
    "respiratory_rate": WebhookEventType.RESPIRATORY_RATE_UPDATED,
    "body_temperature": WebhookEventType.BODY_TEMPERATURE_UPDATED,
    "skin_temperature": WebhookEventType.BODY_TEMPERATURE_UPDATED,
    "stress": WebhookEventType.STRESS_UPDATED,
    "blood_glucose": WebhookEventType.BLOOD_GLUCOSE_UPDATED,
    "blood_pressure_systolic": WebhookEventType.BLOOD_PRESSURE_UPDATED,
    "blood_pressure_diastolic": WebhookEventType.BLOOD_PRESSURE_UPDATED,
}

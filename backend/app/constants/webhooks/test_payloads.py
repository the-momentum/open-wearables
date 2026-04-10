"""Hardcoded example payloads for each webhook event type.

Used by the test endpoint to send a realistic sample message to a registered
endpoint without requiring Svix event-type schemas to be defined.
"""

from app.schemas.webhooks.event_types import WebhookEventType

EXAMPLE_PAYLOADS: dict[str, dict] = {
    WebhookEventType.WORKOUT_CREATED: {
        "type": WebhookEventType.WORKOUT_CREATED,
        "data": {
            "record_id": "00000000-0000-0000-0000-000000000001",
            "user_id": "00000000-0000-0000-0000-000000000002",
            "provider": "garmin",
            "workout_type": "running",
            "start_datetime": "2024-01-01T08:00:00+00:00",
            "end_datetime": "2024-01-01T09:00:00+00:00",
            "duration_seconds": 3600.0,
        },
    },
    WebhookEventType.SLEEP_CREATED: {
        "type": WebhookEventType.SLEEP_CREATED,
        "data": {
            "record_id": "00000000-0000-0000-0000-000000000001",
            "user_id": "00000000-0000-0000-0000-000000000002",
            "provider": "oura",
            "start_datetime": "2024-01-01T22:00:00+00:00",
            "end_datetime": "2024-01-02T06:30:00+00:00",
            "duration_seconds": 30600.0,
        },
    },
    WebhookEventType.ACTIVITY_CREATED: {
        "type": WebhookEventType.ACTIVITY_CREATED,
        "data": {
            "record_id": "00000000-0000-0000-0000-000000000001",
            "user_id": "00000000-0000-0000-0000-000000000002",
            "provider": "garmin",
            "activity_type": "walking",
            "start_datetime": "2024-01-01T12:00:00+00:00",
            "end_datetime": "2024-01-01T12:30:00+00:00",
        },
    },
    WebhookEventType.HEART_RATE_UPDATED: {
        "type": WebhookEventType.HEART_RATE_UPDATED,
        "data": {
            "user_id": "00000000-0000-0000-0000-000000000002",
            "provider": "garmin",
            "series_type": "heart_rate",
            "sample_count": 10,
            "start_datetime": "2024-01-01T08:00:00+00:00",
            "end_datetime": "2024-01-01T09:00:00+00:00",
        },
    },
    WebhookEventType.HEART_RATE_VARIABILITY_UPDATED: {
        "type": WebhookEventType.HEART_RATE_VARIABILITY_UPDATED,
        "data": {
            "user_id": "00000000-0000-0000-0000-000000000002",
            "provider": "oura",
            "series_type": "heart_rate_variability_sdnn",
            "sample_count": 5,
            "start_datetime": "2024-01-01T22:00:00+00:00",
            "end_datetime": "2024-01-02T06:00:00+00:00",
        },
    },
    WebhookEventType.STEPS_UPDATED: {
        "type": WebhookEventType.STEPS_UPDATED,
        "data": {
            "user_id": "00000000-0000-0000-0000-000000000002",
            "provider": "garmin",
            "series_type": "steps",
            "sample_count": 24,
            "start_datetime": "2024-01-01T00:00:00+00:00",
            "end_datetime": "2024-01-01T23:59:00+00:00",
        },
    },
    WebhookEventType.CALORIES_UPDATED: {
        "type": WebhookEventType.CALORIES_UPDATED,
        "data": {
            "user_id": "00000000-0000-0000-0000-000000000002",
            "provider": "garmin",
            "series_type": "energy",
            "sample_count": 24,
            "start_datetime": "2024-01-01T00:00:00+00:00",
            "end_datetime": "2024-01-01T23:59:00+00:00",
        },
    },
    WebhookEventType.SPO2_UPDATED: {
        "type": WebhookEventType.SPO2_UPDATED,
        "data": {
            "user_id": "00000000-0000-0000-0000-000000000002",
            "provider": "oura",
            "series_type": "oxygen_saturation",
            "sample_count": 8,
            "start_datetime": "2024-01-01T22:00:00+00:00",
            "end_datetime": "2024-01-02T06:00:00+00:00",
        },
    },
    WebhookEventType.RESPIRATORY_RATE_UPDATED: {
        "type": WebhookEventType.RESPIRATORY_RATE_UPDATED,
        "data": {
            "user_id": "00000000-0000-0000-0000-000000000002",
            "provider": "oura",
            "series_type": "respiratory_rate",
            "sample_count": 8,
            "start_datetime": "2024-01-01T22:00:00+00:00",
            "end_datetime": "2024-01-02T06:00:00+00:00",
        },
    },
    WebhookEventType.BODY_TEMPERATURE_UPDATED: {
        "type": WebhookEventType.BODY_TEMPERATURE_UPDATED,
        "data": {
            "user_id": "00000000-0000-0000-0000-000000000002",
            "provider": "oura",
            "series_type": "body_temperature",
            "sample_count": 1,
            "start_datetime": "2024-01-01T22:00:00+00:00",
            "end_datetime": "2024-01-02T06:00:00+00:00",
        },
    },
    WebhookEventType.STRESS_UPDATED: {
        "type": WebhookEventType.STRESS_UPDATED,
        "data": {
            "user_id": "00000000-0000-0000-0000-000000000002",
            "provider": "garmin",
            "series_type": "stress",
            "sample_count": 12,
            "start_datetime": "2024-01-01T08:00:00+00:00",
            "end_datetime": "2024-01-01T20:00:00+00:00",
        },
    },
    WebhookEventType.BLOOD_GLUCOSE_UPDATED: {
        "type": WebhookEventType.BLOOD_GLUCOSE_UPDATED,
        "data": {
            "user_id": "00000000-0000-0000-0000-000000000002",
            "provider": "ultrahuman",
            "series_type": "blood_glucose",
            "sample_count": 288,
            "start_datetime": "2024-01-01T00:00:00+00:00",
            "end_datetime": "2024-01-01T23:59:00+00:00",
        },
    },
    WebhookEventType.BLOOD_PRESSURE_UPDATED: {
        "type": WebhookEventType.BLOOD_PRESSURE_UPDATED,
        "data": {
            "user_id": "00000000-0000-0000-0000-000000000002",
            "provider": "garmin",
            "series_type": "blood_pressure_systolic",
            "sample_count": 3,
            "start_datetime": "2024-01-01T08:00:00+00:00",
            "end_datetime": "2024-01-01T20:00:00+00:00",
        },
    },
    WebhookEventType.TIMESERIES_UPDATED: {
        "type": WebhookEventType.TIMESERIES_UPDATED,
        "data": {
            "user_id": "00000000-0000-0000-0000-000000000002",
            "provider": "garmin",
            "series_type": "unknown",
            "sample_count": 10,
            "start_datetime": "2024-01-01T08:00:00+00:00",
            "end_datetime": "2024-01-01T09:00:00+00:00",
        },
    },
}


def get_test_payload(event_type: str) -> dict:
    """Return the example payload for the given event type.

    Falls back to the TIMESERIES_UPDATED example for unknown types.
    """
    return EXAMPLE_PAYLOADS.get(event_type, EXAMPLE_PAYLOADS[WebhookEventType.TIMESERIES_UPDATED])

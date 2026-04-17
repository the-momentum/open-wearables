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
    WebhookEventType.HEART_RATE_CREATED: {
        "type": WebhookEventType.HEART_RATE_CREATED,
        "data": {
            "user_id": "00000000-0000-0000-0000-000000000002",
            "provider": "garmin",
            "series_type": "heart_rate",
            "sample_count": 10,
            "start_datetime": "2024-01-01T08:00:00+00:00",
            "end_datetime": "2024-01-01T09:00:00+00:00",
        },
    },
    WebhookEventType.HEART_RATE_VARIABILITY_CREATED: {
        "type": WebhookEventType.HEART_RATE_VARIABILITY_CREATED,
        "data": {
            "user_id": "00000000-0000-0000-0000-000000000002",
            "provider": "oura",
            "series_type": "heart_rate_variability_sdnn",
            "sample_count": 5,
            "start_datetime": "2024-01-01T22:00:00+00:00",
            "end_datetime": "2024-01-02T06:00:00+00:00",
        },
    },
    WebhookEventType.STEPS_CREATED: {
        "type": WebhookEventType.STEPS_CREATED,
        "data": {
            "user_id": "00000000-0000-0000-0000-000000000002",
            "provider": "garmin",
            "series_type": "steps",
            "sample_count": 24,
            "start_datetime": "2024-01-01T00:00:00+00:00",
            "end_datetime": "2024-01-01T23:59:00+00:00",
        },
    },
    WebhookEventType.CALORIES_CREATED: {
        "type": WebhookEventType.CALORIES_CREATED,
        "data": {
            "user_id": "00000000-0000-0000-0000-000000000002",
            "provider": "garmin",
            "series_type": "energy",
            "sample_count": 24,
            "start_datetime": "2024-01-01T00:00:00+00:00",
            "end_datetime": "2024-01-01T23:59:00+00:00",
        },
    },
    WebhookEventType.SPO2_CREATED: {
        "type": WebhookEventType.SPO2_CREATED,
        "data": {
            "user_id": "00000000-0000-0000-0000-000000000002",
            "provider": "oura",
            "series_type": "oxygen_saturation",
            "sample_count": 8,
            "start_datetime": "2024-01-01T22:00:00+00:00",
            "end_datetime": "2024-01-02T06:00:00+00:00",
        },
    },
    WebhookEventType.RESPIRATORY_RATE_CREATED: {
        "type": WebhookEventType.RESPIRATORY_RATE_CREATED,
        "data": {
            "user_id": "00000000-0000-0000-0000-000000000002",
            "provider": "oura",
            "series_type": "respiratory_rate",
            "sample_count": 8,
            "start_datetime": "2024-01-01T22:00:00+00:00",
            "end_datetime": "2024-01-02T06:00:00+00:00",
        },
    },
    WebhookEventType.BODY_TEMPERATURE_CREATED: {
        "type": WebhookEventType.BODY_TEMPERATURE_CREATED,
        "data": {
            "user_id": "00000000-0000-0000-0000-000000000002",
            "provider": "oura",
            "series_type": "body_temperature",
            "sample_count": 1,
            "start_datetime": "2024-01-01T22:00:00+00:00",
            "end_datetime": "2024-01-02T06:00:00+00:00",
        },
    },
    WebhookEventType.STRESS_CREATED: {
        "type": WebhookEventType.STRESS_CREATED,
        "data": {
            "user_id": "00000000-0000-0000-0000-000000000002",
            "provider": "garmin",
            "series_type": "stress",
            "sample_count": 12,
            "start_datetime": "2024-01-01T08:00:00+00:00",
            "end_datetime": "2024-01-01T20:00:00+00:00",
        },
    },
    WebhookEventType.BLOOD_GLUCOSE_CREATED: {
        "type": WebhookEventType.BLOOD_GLUCOSE_CREATED,
        "data": {
            "user_id": "00000000-0000-0000-0000-000000000002",
            "provider": "ultrahuman",
            "series_type": "blood_glucose",
            "sample_count": 288,
            "start_datetime": "2024-01-01T00:00:00+00:00",
            "end_datetime": "2024-01-01T23:59:00+00:00",
        },
    },
    WebhookEventType.BLOOD_PRESSURE_CREATED: {
        "type": WebhookEventType.BLOOD_PRESSURE_CREATED,
        "data": {
            "user_id": "00000000-0000-0000-0000-000000000002",
            "provider": "garmin",
            "series_type": "blood_pressure_systolic",
            "sample_count": 3,
            "start_datetime": "2024-01-01T08:00:00+00:00",
            "end_datetime": "2024-01-01T20:00:00+00:00",
        },
    },
}


def get_test_payload(event_type: str) -> dict:
    """Return the example payload for the given event type."""
    return EXAMPLE_PAYLOADS.get(event_type, {})

"""Hardcoded example payloads for each webhook event type.

Used by the test endpoint to send a realistic sample message to a registered
endpoint without requiring Svix event-type schemas to be defined.

Field names and structure must match what the real event emitters produce
(see app/services/outgoing_webhooks/events.py).
"""

from app.schemas.webhooks.event_types import WebhookEventType

_USER_ID = "00000000-0000-0000-0000-000000000002"
_RECORD_ID = "00000000-0000-0000-0000-000000000001"
_CONNECTION_ID = "00000000-0000-0000-0000-000000000003"

_SOURCE_GARMIN = {"provider": "garmin", "device": "Garmin Fenix 7"}
_SOURCE_OURA = {"provider": "oura", "device": "Oura Ring Gen3"}
_SOURCE_APPLE = {"provider": "apple", "device": "Apple Watch Series 9"}


def _ts_payload(event_type: str, series_type: str, provider: str, unit: str, sample_value: float) -> dict:
    """Build a timeseries group or granular event payload with one example sample."""
    source = {"provider": provider, "device": None}
    return {
        "type": event_type,
        "data": {
            "user_id": _USER_ID,
            "provider": provider,
            "series_type": series_type,
            "sample_count": 1,
            "start_time": "2024-01-01T08:00:00+00:00",
            "end_time": "2024-01-01T08:01:00+00:00",
            "samples": [
                {
                    "timestamp": "2024-01-01T08:00:00+00:00",
                    "zone_offset": "+00:00",
                    "type": series_type,
                    "value": sample_value,
                    "unit": unit,
                    "source": source,
                }
            ],
        },
    }


EXAMPLE_PAYLOADS: dict[str, dict] = {
    # ------------------------------------------------------------------
    # Provider connection
    # ------------------------------------------------------------------
    WebhookEventType.CONNECTION_CREATED: {
        "type": WebhookEventType.CONNECTION_CREATED,
        "data": {
            "user_id": _USER_ID,
            "provider": "garmin",
            "connection_id": _CONNECTION_ID,
            "connected_at": "2024-01-01T08:00:00+00:00",
        },
    },
    # ------------------------------------------------------------------
    # Session events
    # ------------------------------------------------------------------
    WebhookEventType.WORKOUT_CREATED: {
        "type": WebhookEventType.WORKOUT_CREATED,
        "data": {
            "id": _RECORD_ID,
            "user_id": _USER_ID,
            "type": "running",
            "start_time": "2024-01-01T08:00:00+00:00",
            "end_time": "2024-01-01T09:00:00+00:00",
            "zone_offset": "+00:00",
            "duration_seconds": 3600.0,
            "source": _SOURCE_GARMIN,
            "calories_kcal": 450.0,
            "distance_meters": 8500.0,
            "avg_heart_rate_bpm": 155,
            "max_heart_rate_bpm": 178,
            "avg_pace_sec_per_km": 424,
            "elevation_gain_meters": 120.0,
        },
    },
    WebhookEventType.SLEEP_CREATED: {
        "type": WebhookEventType.SLEEP_CREATED,
        "data": {
            "id": _RECORD_ID,
            "user_id": _USER_ID,
            "start_time": "2024-01-01T22:00:00+00:00",
            "end_time": "2024-01-02T06:30:00+00:00",
            "zone_offset": "+00:00",
            "duration_seconds": 30600.0,
            "source": _SOURCE_OURA,
            "efficiency_percent": 88.5,
            "stages": {
                "awake_minutes": 12,
                "light_minutes": 210,
                "deep_minutes": 90,
                "rem_minutes": 95,
            },
            "is_nap": False,
        },
    },
    # ------------------------------------------------------------------
    # Timeseries — GROUP events
    # ------------------------------------------------------------------
    WebhookEventType.HEART_RATE_CREATED: _ts_payload(
        WebhookEventType.HEART_RATE_CREATED, "heart_rate", "garmin", "bpm", 72.0
    ),
    WebhookEventType.HEART_RATE_VARIABILITY_CREATED: _ts_payload(
        WebhookEventType.HEART_RATE_VARIABILITY_CREATED, "heart_rate_variability_sdnn", "oura", "ms", 48.0
    ),
    WebhookEventType.STEPS_CREATED: _ts_payload(WebhookEventType.STEPS_CREATED, "steps", "garmin", "count", 8432.0),
    WebhookEventType.CALORIES_CREATED: _ts_payload(
        WebhookEventType.CALORIES_CREATED, "energy", "garmin", "kcal", 320.0
    ),
    WebhookEventType.SPO2_CREATED: _ts_payload(WebhookEventType.SPO2_CREATED, "oxygen_saturation", "oura", "%", 97.0),
    WebhookEventType.RESPIRATORY_RATE_CREATED: _ts_payload(
        WebhookEventType.RESPIRATORY_RATE_CREATED, "respiratory_rate", "oura", "breaths/min", 14.5
    ),
    WebhookEventType.BODY_TEMPERATURE_CREATED: _ts_payload(
        WebhookEventType.BODY_TEMPERATURE_CREATED, "skin_temperature", "oura", "°C", 36.1
    ),
    WebhookEventType.STRESS_CREATED: _ts_payload(
        WebhookEventType.STRESS_CREATED, "garmin_stress_level", "garmin", "score", 32.0
    ),
    WebhookEventType.BLOOD_GLUCOSE_CREATED: _ts_payload(
        WebhookEventType.BLOOD_GLUCOSE_CREATED, "blood_glucose", "ultrahuman", "mg/dL", 95.0
    ),
    WebhookEventType.BLOOD_PRESSURE_CREATED: _ts_payload(
        WebhookEventType.BLOOD_PRESSURE_CREATED, "blood_pressure_systolic", "garmin", "mmHg", 118.0
    ),
    WebhookEventType.BODY_COMPOSITION_CREATED: _ts_payload(
        WebhookEventType.BODY_COMPOSITION_CREATED, "weight", "garmin", "kg", 75.4
    ),
    WebhookEventType.FITNESS_METRICS_CREATED: _ts_payload(
        WebhookEventType.FITNESS_METRICS_CREATED, "vo2_max", "garmin", "mL/kg/min", 52.0
    ),
    WebhookEventType.RECOVERY_SCORE_CREATED: _ts_payload(
        WebhookEventType.RECOVERY_SCORE_CREATED, "recovery_score", "oura", "score", 78.0
    ),
    WebhookEventType.ACTIVITY_CREATED_TIMESERIES: _ts_payload(
        WebhookEventType.ACTIVITY_CREATED_TIMESERIES, "stand_time", "apple", "min", 45.0
    ),
    WebhookEventType.WORKOUT_METRICS_CREATED: _ts_payload(
        WebhookEventType.WORKOUT_METRICS_CREATED, "cadence", "garmin", "rpm", 88.0
    ),
    WebhookEventType.ENVIRONMENTAL_CREATED: _ts_payload(
        WebhookEventType.ENVIRONMENTAL_CREATED, "environmental_audio_exposure", "apple", "dBASPL", 72.0
    ),
    # ------------------------------------------------------------------
    # Timeseries — GRANULAR (series.*) events
    # ------------------------------------------------------------------
    # Heart & Cardiovascular
    WebhookEventType.SERIES_HEART_RATE: _ts_payload(
        WebhookEventType.SERIES_HEART_RATE, "heart_rate", "garmin", "bpm", 72.0
    ),
    WebhookEventType.SERIES_RESTING_HEART_RATE: _ts_payload(
        WebhookEventType.SERIES_RESTING_HEART_RATE, "resting_heart_rate", "garmin", "bpm", 52.0
    ),
    WebhookEventType.SERIES_HEART_RATE_RECOVERY_ONE_MINUTE: _ts_payload(
        WebhookEventType.SERIES_HEART_RATE_RECOVERY_ONE_MINUTE, "heart_rate_recovery_one_minute", "garmin", "bpm", 24.0
    ),
    WebhookEventType.SERIES_WALKING_HEART_RATE_AVERAGE: _ts_payload(
        WebhookEventType.SERIES_WALKING_HEART_RATE_AVERAGE, "walking_heart_rate_average", "apple", "bpm", 98.0
    ),
    WebhookEventType.SERIES_ATRIAL_FIBRILLATION_BURDEN: _ts_payload(
        WebhookEventType.SERIES_ATRIAL_FIBRILLATION_BURDEN, "atrial_fibrillation_burden", "apple", "%", 0.0
    ),
    # HRV
    WebhookEventType.SERIES_HEART_RATE_VARIABILITY_SDNN: _ts_payload(
        WebhookEventType.SERIES_HEART_RATE_VARIABILITY_SDNN, "heart_rate_variability_sdnn", "oura", "ms", 48.0
    ),
    WebhookEventType.SERIES_HEART_RATE_VARIABILITY_RMSSD: _ts_payload(
        WebhookEventType.SERIES_HEART_RATE_VARIABILITY_RMSSD, "heart_rate_variability_rmssd", "garmin", "ms", 42.0
    ),
    # Recovery
    WebhookEventType.SERIES_GARMIN_BODY_BATTERY: _ts_payload(
        WebhookEventType.SERIES_GARMIN_BODY_BATTERY, "garmin_body_battery", "garmin", "score", 65.0
    ),
    # SpO2
    WebhookEventType.SERIES_OXYGEN_SATURATION: _ts_payload(
        WebhookEventType.SERIES_OXYGEN_SATURATION, "oxygen_saturation", "oura", "%", 97.0
    ),
    WebhookEventType.SERIES_PERIPHERAL_PERFUSION_INDEX: _ts_payload(
        WebhookEventType.SERIES_PERIPHERAL_PERFUSION_INDEX, "peripheral_perfusion_index", "apple", "%", 2.1
    ),
    # Blood glucose / alcohol / insulin
    WebhookEventType.SERIES_BLOOD_GLUCOSE: _ts_payload(
        WebhookEventType.SERIES_BLOOD_GLUCOSE, "blood_glucose", "ultrahuman", "mg/dL", 95.0
    ),
    WebhookEventType.SERIES_BLOOD_ALCOHOL_CONTENT: _ts_payload(
        WebhookEventType.SERIES_BLOOD_ALCOHOL_CONTENT, "blood_alcohol_content", "apple", "g/dL", 0.0
    ),
    WebhookEventType.SERIES_INSULIN_DELIVERY: _ts_payload(
        WebhookEventType.SERIES_INSULIN_DELIVERY, "insulin_delivery", "apple", "IU", 4.0
    ),
    # Blood pressure
    WebhookEventType.SERIES_BLOOD_PRESSURE_SYSTOLIC: _ts_payload(
        WebhookEventType.SERIES_BLOOD_PRESSURE_SYSTOLIC, "blood_pressure_systolic", "garmin", "mmHg", 118.0
    ),
    WebhookEventType.SERIES_BLOOD_PRESSURE_DIASTOLIC: _ts_payload(
        WebhookEventType.SERIES_BLOOD_PRESSURE_DIASTOLIC, "blood_pressure_diastolic", "garmin", "mmHg", 76.0
    ),
    # Respiratory
    WebhookEventType.SERIES_RESPIRATORY_RATE: _ts_payload(
        WebhookEventType.SERIES_RESPIRATORY_RATE, "respiratory_rate", "oura", "breaths/min", 14.5
    ),
    WebhookEventType.SERIES_SLEEPING_BREATHING_DISTURBANCES: _ts_payload(
        WebhookEventType.SERIES_SLEEPING_BREATHING_DISTURBANCES,
        "sleeping_breathing_disturbances",
        "oura",
        "count/h",
        2.1,
    ),
    WebhookEventType.SERIES_BREATHING_DISTURBANCE_INDEX: _ts_payload(
        WebhookEventType.SERIES_BREATHING_DISTURBANCE_INDEX, "breathing_disturbance_index", "oura", "count/h", 1.5
    ),
    WebhookEventType.SERIES_FORCED_VITAL_CAPACITY: _ts_payload(
        WebhookEventType.SERIES_FORCED_VITAL_CAPACITY, "forced_vital_capacity", "apple", "L", 4.8
    ),
    WebhookEventType.SERIES_FORCED_EXPIRATORY_VOLUME_1: _ts_payload(
        WebhookEventType.SERIES_FORCED_EXPIRATORY_VOLUME_1, "forced_expiratory_volume_1", "apple", "L", 3.9
    ),
    WebhookEventType.SERIES_PEAK_EXPIRATORY_FLOW_RATE: _ts_payload(
        WebhookEventType.SERIES_PEAK_EXPIRATORY_FLOW_RATE, "peak_expiratory_flow_rate", "apple", "L/min", 550.0
    ),
    # Body composition
    WebhookEventType.SERIES_HEIGHT: _ts_payload(WebhookEventType.SERIES_HEIGHT, "height", "apple", "cm", 178.0),
    WebhookEventType.SERIES_WEIGHT: _ts_payload(WebhookEventType.SERIES_WEIGHT, "weight", "garmin", "kg", 75.4),
    WebhookEventType.SERIES_BODY_FAT_PERCENTAGE: _ts_payload(
        WebhookEventType.SERIES_BODY_FAT_PERCENTAGE, "body_fat_percentage", "garmin", "%", 18.2
    ),
    WebhookEventType.SERIES_BODY_MASS_INDEX: _ts_payload(
        WebhookEventType.SERIES_BODY_MASS_INDEX, "body_mass_index", "apple", "kg/m²", 23.8
    ),
    WebhookEventType.SERIES_LEAN_BODY_MASS: _ts_payload(
        WebhookEventType.SERIES_LEAN_BODY_MASS, "lean_body_mass", "apple", "kg", 61.7
    ),
    WebhookEventType.SERIES_BODY_FAT_MASS: _ts_payload(
        WebhookEventType.SERIES_BODY_FAT_MASS, "body_fat_mass", "apple", "kg", 13.7
    ),
    WebhookEventType.SERIES_SKELETAL_MUSCLE_MASS: _ts_payload(
        WebhookEventType.SERIES_SKELETAL_MUSCLE_MASS, "skeletal_muscle_mass", "garmin", "kg", 35.2
    ),
    WebhookEventType.SERIES_WAIST_CIRCUMFERENCE: _ts_payload(
        WebhookEventType.SERIES_WAIST_CIRCUMFERENCE, "waist_circumference", "apple", "cm", 84.0
    ),
    # Body temperature
    WebhookEventType.SERIES_BODY_TEMPERATURE: _ts_payload(
        WebhookEventType.SERIES_BODY_TEMPERATURE, "body_temperature", "apple", "°C", 36.6
    ),
    WebhookEventType.SERIES_SKIN_TEMPERATURE: _ts_payload(
        WebhookEventType.SERIES_SKIN_TEMPERATURE, "skin_temperature", "oura", "°C", 36.1
    ),
    WebhookEventType.SERIES_SKIN_TEMPERATURE_DEVIATION: _ts_payload(
        WebhookEventType.SERIES_SKIN_TEMPERATURE_DEVIATION, "skin_temperature_deviation", "oura", "°C", -0.3
    ),
    WebhookEventType.SERIES_SKIN_TEMPERATURE_TREND_DEVIATION: _ts_payload(
        WebhookEventType.SERIES_SKIN_TEMPERATURE_TREND_DEVIATION, "skin_temperature_trend_deviation", "apple", "°C", 0.1
    ),
    WebhookEventType.SERIES_GARMIN_SKIN_TEMPERATURE: _ts_payload(
        WebhookEventType.SERIES_GARMIN_SKIN_TEMPERATURE, "garmin_skin_temperature", "garmin", "°C", 35.8
    ),
    # Stress
    WebhookEventType.SERIES_GARMIN_STRESS_LEVEL: _ts_payload(
        WebhookEventType.SERIES_GARMIN_STRESS_LEVEL, "garmin_stress_level", "garmin", "score", 32.0
    ),
    WebhookEventType.SERIES_ELECTRODERMAL_ACTIVITY: _ts_payload(
        WebhookEventType.SERIES_ELECTRODERMAL_ACTIVITY, "electrodermal_activity", "apple", "S", 0.05
    ),
    # Fitness metrics
    WebhookEventType.SERIES_VO2_MAX: _ts_payload(
        WebhookEventType.SERIES_VO2_MAX, "vo2_max", "garmin", "mL/kg/min", 52.0
    ),
    WebhookEventType.SERIES_SIX_MINUTE_WALK_TEST_DISTANCE: _ts_payload(
        WebhookEventType.SERIES_SIX_MINUTE_WALK_TEST_DISTANCE, "six_minute_walk_test_distance", "apple", "m", 542.0
    ),
    WebhookEventType.SERIES_CARDIOVASCULAR_AGE: _ts_payload(
        WebhookEventType.SERIES_CARDIOVASCULAR_AGE, "cardiovascular_age", "apple", "years", 34.0
    ),
    WebhookEventType.SERIES_GARMIN_FITNESS_AGE: _ts_payload(
        WebhookEventType.SERIES_GARMIN_FITNESS_AGE, "garmin_fitness_age", "garmin", "years", 31.0
    ),
    # Steps & calories
    WebhookEventType.SERIES_STEPS: _ts_payload(WebhookEventType.SERIES_STEPS, "steps", "garmin", "count", 8432.0),
    WebhookEventType.SERIES_ENERGY: _ts_payload(WebhookEventType.SERIES_ENERGY, "energy", "garmin", "kcal", 320.0),
    WebhookEventType.SERIES_BASAL_ENERGY: _ts_payload(
        WebhookEventType.SERIES_BASAL_ENERGY, "basal_energy", "apple", "kcal", 1850.0
    ),
    # Activity basic
    WebhookEventType.SERIES_STAND_TIME: _ts_payload(
        WebhookEventType.SERIES_STAND_TIME, "stand_time", "apple", "min", 45.0
    ),
    WebhookEventType.SERIES_EXERCISE_TIME: _ts_payload(
        WebhookEventType.SERIES_EXERCISE_TIME, "exercise_time", "apple", "min", 32.0
    ),
    WebhookEventType.SERIES_PHYSICAL_EFFORT: _ts_payload(
        WebhookEventType.SERIES_PHYSICAL_EFFORT, "physical_effort", "apple", "MET·min", 4.2
    ),
    WebhookEventType.SERIES_FLIGHTS_CLIMBED: _ts_payload(
        WebhookEventType.SERIES_FLIGHTS_CLIMBED, "flights_climbed", "apple", "count", 8.0
    ),
    WebhookEventType.SERIES_AVERAGE_MET: _ts_payload(
        WebhookEventType.SERIES_AVERAGE_MET, "average_met", "apple", "MET", 1.4
    ),
    WebhookEventType.SERIES_PUSH_COUNT: _ts_payload(
        WebhookEventType.SERIES_PUSH_COUNT, "push_count", "apple", "count", 0.0
    ),
    WebhookEventType.SERIES_NUMBER_OF_TIMES_FALLEN: _ts_payload(
        WebhookEventType.SERIES_NUMBER_OF_TIMES_FALLEN, "number_of_times_fallen", "apple", "count", 0.0
    ),
    WebhookEventType.SERIES_NUMBER_OF_ALCOHOLIC_BEVERAGES: _ts_payload(
        WebhookEventType.SERIES_NUMBER_OF_ALCOHOLIC_BEVERAGES, "number_of_alcoholic_beverages", "apple", "count", 1.0
    ),
    WebhookEventType.SERIES_NIKE_FUEL: _ts_payload(
        WebhookEventType.SERIES_NIKE_FUEL, "nike_fuel", "apple", "NikeFuel", 2100.0
    ),
    WebhookEventType.SERIES_HYDRATION: _ts_payload(
        WebhookEventType.SERIES_HYDRATION, "hydration", "apple", "mL", 2200.0
    ),
    # Activity distance
    WebhookEventType.SERIES_DISTANCE_WALKING_RUNNING: _ts_payload(
        WebhookEventType.SERIES_DISTANCE_WALKING_RUNNING, "distance_walking_running", "apple", "m", 6240.0
    ),
    WebhookEventType.SERIES_DISTANCE_CYCLING: _ts_payload(
        WebhookEventType.SERIES_DISTANCE_CYCLING, "distance_cycling", "garmin", "m", 28500.0
    ),
    WebhookEventType.SERIES_DISTANCE_SWIMMING: _ts_payload(
        WebhookEventType.SERIES_DISTANCE_SWIMMING, "distance_swimming", "apple", "m", 1500.0
    ),
    WebhookEventType.SERIES_DISTANCE_DOWNHILL_SNOW_SPORTS: _ts_payload(
        WebhookEventType.SERIES_DISTANCE_DOWNHILL_SNOW_SPORTS, "distance_downhill_snow_sports", "apple", "m", 12000.0
    ),
    WebhookEventType.SERIES_DISTANCE_OTHER: _ts_payload(
        WebhookEventType.SERIES_DISTANCE_OTHER, "distance_other", "apple", "m", 500.0
    ),
    # Workout / sport metrics
    WebhookEventType.SERIES_CADENCE: _ts_payload(WebhookEventType.SERIES_CADENCE, "cadence", "garmin", "rpm", 88.0),
    WebhookEventType.SERIES_POWER: _ts_payload(WebhookEventType.SERIES_POWER, "power", "garmin", "W", 220.0),
    WebhookEventType.SERIES_SPEED: _ts_payload(WebhookEventType.SERIES_SPEED, "speed", "garmin", "m/s", 2.8),
    WebhookEventType.SERIES_WORKOUT_EFFORT_SCORE: _ts_payload(
        WebhookEventType.SERIES_WORKOUT_EFFORT_SCORE, "workout_effort_score", "apple", "score", 4.0
    ),
    WebhookEventType.SERIES_ESTIMATED_WORKOUT_EFFORT_SCORE: _ts_payload(
        WebhookEventType.SERIES_ESTIMATED_WORKOUT_EFFORT_SCORE,
        "estimated_workout_effort_score",
        "apple",
        "score",
        3.0,
    ),
    WebhookEventType.SERIES_WALKING_STEP_LENGTH: _ts_payload(
        WebhookEventType.SERIES_WALKING_STEP_LENGTH, "walking_step_length", "apple", "m", 0.72
    ),
    WebhookEventType.SERIES_WALKING_SPEED: _ts_payload(
        WebhookEventType.SERIES_WALKING_SPEED, "walking_speed", "apple", "m/s", 1.4
    ),
    WebhookEventType.SERIES_WALKING_DOUBLE_SUPPORT_PERCENTAGE: _ts_payload(
        WebhookEventType.SERIES_WALKING_DOUBLE_SUPPORT_PERCENTAGE,
        "walking_double_support_percentage",
        "apple",
        "%",
        27.0,
    ),  # noqa: E501
    WebhookEventType.SERIES_WALKING_ASYMMETRY_PERCENTAGE: _ts_payload(
        WebhookEventType.SERIES_WALKING_ASYMMETRY_PERCENTAGE, "walking_asymmetry_percentage", "apple", "%", 4.5
    ),
    WebhookEventType.SERIES_WALKING_STEADINESS: _ts_payload(
        WebhookEventType.SERIES_WALKING_STEADINESS, "walking_steadiness", "apple", "%", 95.0
    ),
    WebhookEventType.SERIES_STAIR_DESCENT_SPEED: _ts_payload(
        WebhookEventType.SERIES_STAIR_DESCENT_SPEED, "stair_descent_speed", "apple", "floors/min", 0.6
    ),
    WebhookEventType.SERIES_STAIR_ASCENT_SPEED: _ts_payload(
        WebhookEventType.SERIES_STAIR_ASCENT_SPEED, "stair_ascent_speed", "apple", "floors/min", 0.5
    ),
    WebhookEventType.SERIES_RUNNING_POWER: _ts_payload(
        WebhookEventType.SERIES_RUNNING_POWER, "running_power", "garmin", "W", 245.0
    ),
    WebhookEventType.SERIES_RUNNING_SPEED: _ts_payload(
        WebhookEventType.SERIES_RUNNING_SPEED, "running_speed", "garmin", "m/s", 3.1
    ),
    WebhookEventType.SERIES_RUNNING_VERTICAL_OSCILLATION: _ts_payload(
        WebhookEventType.SERIES_RUNNING_VERTICAL_OSCILLATION, "running_vertical_oscillation", "garmin", "cm", 8.2
    ),
    WebhookEventType.SERIES_RUNNING_GROUND_CONTACT_TIME: _ts_payload(
        WebhookEventType.SERIES_RUNNING_GROUND_CONTACT_TIME, "running_ground_contact_time", "garmin", "ms", 240.0
    ),
    WebhookEventType.SERIES_RUNNING_STRIDE_LENGTH: _ts_payload(
        WebhookEventType.SERIES_RUNNING_STRIDE_LENGTH, "running_stride_length", "garmin", "m", 1.24
    ),
    WebhookEventType.SERIES_SWIMMING_STROKE_COUNT: _ts_payload(
        WebhookEventType.SERIES_SWIMMING_STROKE_COUNT, "swimming_stroke_count", "apple", "count", 1240.0
    ),
    WebhookEventType.SERIES_UNDERWATER_DEPTH: _ts_payload(
        WebhookEventType.SERIES_UNDERWATER_DEPTH, "underwater_depth", "apple", "m", 12.5
    ),
    # Environmental
    WebhookEventType.SERIES_ENVIRONMENTAL_AUDIO_EXPOSURE: _ts_payload(
        WebhookEventType.SERIES_ENVIRONMENTAL_AUDIO_EXPOSURE, "environmental_audio_exposure", "apple", "dBASPL", 72.0
    ),
    WebhookEventType.SERIES_HEADPHONE_AUDIO_EXPOSURE: _ts_payload(
        WebhookEventType.SERIES_HEADPHONE_AUDIO_EXPOSURE, "headphone_audio_exposure", "apple", "dBASPL", 68.0
    ),
    WebhookEventType.SERIES_ENVIRONMENTAL_SOUND_REDUCTION: _ts_payload(
        WebhookEventType.SERIES_ENVIRONMENTAL_SOUND_REDUCTION, "environmental_sound_reduction", "apple", "dB", 22.0
    ),
    WebhookEventType.SERIES_TIME_IN_DAYLIGHT: _ts_payload(
        WebhookEventType.SERIES_TIME_IN_DAYLIGHT, "time_in_daylight", "apple", "min", 85.0
    ),
    WebhookEventType.SERIES_WATER_TEMPERATURE: _ts_payload(
        WebhookEventType.SERIES_WATER_TEMPERATURE, "water_temperature", "garmin", "°C", 22.0
    ),
    WebhookEventType.SERIES_UV_EXPOSURE: _ts_payload(
        WebhookEventType.SERIES_UV_EXPOSURE, "uv_exposure", "apple", "J/m²", 1200.0
    ),
    WebhookEventType.SERIES_INHALER_USAGE: _ts_payload(
        WebhookEventType.SERIES_INHALER_USAGE, "inhaler_usage", "apple", "count", 1.0
    ),
    WebhookEventType.SERIES_WEATHER_TEMPERATURE: _ts_payload(
        WebhookEventType.SERIES_WEATHER_TEMPERATURE, "weather_temperature", "garmin", "°C", 18.0
    ),
    WebhookEventType.SERIES_WEATHER_HUMIDITY: _ts_payload(
        WebhookEventType.SERIES_WEATHER_HUMIDITY, "weather_humidity", "garmin", "%", 62.0
    ),
}


def get_test_payload(event_type: str) -> dict:
    """Return the example payload for the given event type."""
    return EXAMPLE_PAYLOADS.get(event_type, {})

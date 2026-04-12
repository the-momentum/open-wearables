"""Maps SeriesType slugs to their outgoing webhook event type.

Used by the timeseries emit helper to select the most specific event type
for a given measurement kind. Falls back to ``WebhookEventType.TIMESERIES_CREATED``
when the series type is not listed here.
"""

from app.schemas.webhooks.event_types import WebhookEventType

SERIES_TYPE_TO_WEBHOOK_EVENT: dict[str, str] = {
    # Heart & Cardiovascular
    "heart_rate": WebhookEventType.HEART_RATE_CREATED,
    "resting_heart_rate": WebhookEventType.HEART_RATE_CREATED,
    "heart_rate_recovery_one_minute": WebhookEventType.HEART_RATE_CREATED,
    "walking_heart_rate_average": WebhookEventType.HEART_RATE_CREATED,
    "atrial_fibrillation_burden": WebhookEventType.HEART_RATE_CREATED,
    "heart_rate_variability_sdnn": WebhookEventType.HEART_RATE_VARIABILITY_CREATED,
    "heart_rate_variability_rmssd": WebhookEventType.HEART_RATE_VARIABILITY_CREATED,
    "recovery_score": WebhookEventType.RECOVERY_SCORE_CREATED,
    "garmin_body_battery": WebhookEventType.RECOVERY_SCORE_CREATED,
    # Blood & Respiratory
    "oxygen_saturation": WebhookEventType.SPO2_CREATED,
    "peripheral_perfusion_index": WebhookEventType.SPO2_CREATED,
    "blood_glucose": WebhookEventType.BLOOD_GLUCOSE_CREATED,
    "blood_alcohol_content": WebhookEventType.BLOOD_GLUCOSE_CREATED,
    "insulin_delivery": WebhookEventType.BLOOD_GLUCOSE_CREATED,
    "blood_pressure_systolic": WebhookEventType.BLOOD_PRESSURE_CREATED,
    "blood_pressure_diastolic": WebhookEventType.BLOOD_PRESSURE_CREATED,
    "respiratory_rate": WebhookEventType.RESPIRATORY_RATE_CREATED,
    "sleeping_breathing_disturbances": WebhookEventType.RESPIRATORY_RATE_CREATED,
    "breathing_disturbance_index": WebhookEventType.RESPIRATORY_RATE_CREATED,
    "forced_vital_capacity": WebhookEventType.RESPIRATORY_RATE_CREATED,
    "forced_expiratory_volume_1": WebhookEventType.RESPIRATORY_RATE_CREATED,
    "peak_expiratory_flow_rate": WebhookEventType.RESPIRATORY_RATE_CREATED,
    # Body Composition
    "height": WebhookEventType.BODY_COMPOSITION_CREATED,
    "weight": WebhookEventType.BODY_COMPOSITION_CREATED,
    "body_fat_percentage": WebhookEventType.BODY_COMPOSITION_CREATED,
    "body_mass_index": WebhookEventType.BODY_COMPOSITION_CREATED,
    "lean_body_mass": WebhookEventType.BODY_COMPOSITION_CREATED,
    "body_fat_mass": WebhookEventType.BODY_COMPOSITION_CREATED,
    "skeletal_muscle_mass": WebhookEventType.BODY_COMPOSITION_CREATED,
    "waist_circumference": WebhookEventType.BODY_COMPOSITION_CREATED,
    # Body Temperature
    "body_temperature": WebhookEventType.BODY_TEMPERATURE_CREATED,
    "skin_temperature": WebhookEventType.BODY_TEMPERATURE_CREATED,
    "skin_temperature_deviation": WebhookEventType.BODY_TEMPERATURE_CREATED,
    "skin_temperature_trend_deviation": WebhookEventType.BODY_TEMPERATURE_CREATED,
    "garmin_skin_temperature": WebhookEventType.BODY_TEMPERATURE_CREATED,
    # Stress
    "garmin_stress_level": WebhookEventType.STRESS_CREATED,
    "electrodermal_activity": WebhookEventType.STRESS_CREATED,
    # Fitness Metrics
    "vo2_max": WebhookEventType.FITNESS_METRICS_CREATED,
    "six_minute_walk_test_distance": WebhookEventType.FITNESS_METRICS_CREATED,
    "cardiovascular_age": WebhookEventType.FITNESS_METRICS_CREATED,
    "garmin_fitness_age": WebhookEventType.FITNESS_METRICS_CREATED,
    # Activity Basic
    "steps": WebhookEventType.STEPS_CREATED,
    "energy": WebhookEventType.CALORIES_CREATED,
    "basal_energy": WebhookEventType.CALORIES_CREATED,
    "stand_time": WebhookEventType.ACTIVITY_CREATED_TIMESERIES,
    "exercise_time": WebhookEventType.ACTIVITY_CREATED_TIMESERIES,
    "physical_effort": WebhookEventType.ACTIVITY_CREATED_TIMESERIES,
    "flights_climbed": WebhookEventType.ACTIVITY_CREATED_TIMESERIES,
    "average_met": WebhookEventType.ACTIVITY_CREATED_TIMESERIES,
    "push_count": WebhookEventType.ACTIVITY_CREATED_TIMESERIES,
    "number_of_times_fallen": WebhookEventType.ACTIVITY_CREATED_TIMESERIES,
    "number_of_alcoholic_beverages": WebhookEventType.ACTIVITY_CREATED_TIMESERIES,
    "nike_fuel": WebhookEventType.ACTIVITY_CREATED_TIMESERIES,
    "hydration": WebhookEventType.ACTIVITY_CREATED_TIMESERIES,
    # Activity Distance
    "distance_walking_running": WebhookEventType.ACTIVITY_CREATED_TIMESERIES,
    "distance_cycling": WebhookEventType.ACTIVITY_CREATED_TIMESERIES,
    "distance_swimming": WebhookEventType.ACTIVITY_CREATED_TIMESERIES,
    "distance_downhill_snow_sports": WebhookEventType.ACTIVITY_CREATED_TIMESERIES,
    "distance_other": WebhookEventType.ACTIVITY_CREATED_TIMESERIES,
    # Workout / Sport Metrics
    "cadence": WebhookEventType.WORKOUT_METRICS_CREATED,
    "power": WebhookEventType.WORKOUT_METRICS_CREATED,
    "speed": WebhookEventType.WORKOUT_METRICS_CREATED,
    "workout_effort_score": WebhookEventType.WORKOUT_METRICS_CREATED,
    "estimated_workout_effort_score": WebhookEventType.WORKOUT_METRICS_CREATED,
    "walking_step_length": WebhookEventType.WORKOUT_METRICS_CREATED,
    "walking_speed": WebhookEventType.WORKOUT_METRICS_CREATED,
    "walking_double_support_percentage": WebhookEventType.WORKOUT_METRICS_CREATED,
    "walking_asymmetry_percentage": WebhookEventType.WORKOUT_METRICS_CREATED,
    "walking_steadiness": WebhookEventType.WORKOUT_METRICS_CREATED,
    "stair_descent_speed": WebhookEventType.WORKOUT_METRICS_CREATED,
    "stair_ascent_speed": WebhookEventType.WORKOUT_METRICS_CREATED,
    "running_power": WebhookEventType.WORKOUT_METRICS_CREATED,
    "running_speed": WebhookEventType.WORKOUT_METRICS_CREATED,
    "running_vertical_oscillation": WebhookEventType.WORKOUT_METRICS_CREATED,
    "running_ground_contact_time": WebhookEventType.WORKOUT_METRICS_CREATED,
    "running_stride_length": WebhookEventType.WORKOUT_METRICS_CREATED,
    "swimming_stroke_count": WebhookEventType.WORKOUT_METRICS_CREATED,
    "underwater_depth": WebhookEventType.WORKOUT_METRICS_CREATED,
    # Environmental
    "environmental_audio_exposure": WebhookEventType.ENVIRONMENTAL_CREATED,
    "headphone_audio_exposure": WebhookEventType.ENVIRONMENTAL_CREATED,
    "environmental_sound_reduction": WebhookEventType.ENVIRONMENTAL_CREATED,
    "time_in_daylight": WebhookEventType.ENVIRONMENTAL_CREATED,
    "water_temperature": WebhookEventType.ENVIRONMENTAL_CREATED,
    "uv_exposure": WebhookEventType.ENVIRONMENTAL_CREATED,
    "inhaler_usage": WebhookEventType.ENVIRONMENTAL_CREATED,
    "weather_temperature": WebhookEventType.ENVIRONMENTAL_CREATED,
    "weather_humidity": WebhookEventType.ENVIRONMENTAL_CREATED,
}

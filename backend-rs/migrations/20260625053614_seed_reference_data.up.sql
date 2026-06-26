-- Default archival settings singleton.
INSERT INTO archival_settings (
  id,
  archive_after_days,
  delete_after_days
)
VALUES
  (1, NULL, NULL)
ON CONFLICT (id) DO NOTHING;

-- Default device type priority. Lower number means higher priority.
INSERT INTO device_type_priority (
  id,
  device_type,
  priority,
  updated_at
)
VALUES
  ('00000000-0000-7000-8000-000000000001', 'watch', 1, now()),
  ('00000000-0000-7000-8000-000000000002', 'band', 2, now()),
  ('00000000-0000-7000-8000-000000000003', 'ring', 3, now()),
  ('00000000-0000-7000-8000-000000000004', 'phone', 4, now()),
  ('00000000-0000-7000-8000-000000000005', 'scale', 5, now()),
  ('00000000-0000-7000-8000-000000000006', 'other', 6, now()),
  ('00000000-0000-7000-8000-000000000099', 'unknown', 99, now())
ON CONFLICT (device_type) DO UPDATE SET
  priority = EXCLUDED.priority,
  updated_at = now();

-- Default provider priority. Lower number means higher priority.
INSERT INTO provider_priority (
  id,
  provider,
  priority,
  updated_at
)
VALUES
  ('00000000-0000-7000-8001-000000000001', 'apple', 1, now()),
  ('00000000-0000-7000-8001-000000000002', 'garmin', 2, now()),
  ('00000000-0000-7000-8001-000000000003', 'polar', 3, now()),
  ('00000000-0000-7000-8001-000000000004', 'suunto', 4, now()),
  ('00000000-0000-7000-8001-000000000005', 'whoop', 5, now())
ON CONFLICT (provider) DO UPDATE SET
  priority = EXCLUDED.priority,
  updated_at = now();

-- Default provider settings.
INSERT INTO provider_settings (
  provider,
  is_enabled,
  live_sync_mode
)
VALUES
  ('apple', true, NULL),
  ('samsung', true, NULL),
  ('google', true, NULL),
  ('garmin', true, 'webhook'),
  ('polar', true, 'pull'),
  ('suunto', true, 'pull'),
  ('whoop', true, 'pull'),
  ('strava', true, 'pull'),
  ('oura', true, 'pull'),
  ('fitbit', true, 'pull'),
  ('ultrahuman', true, 'pull')
ON CONFLICT (provider) DO UPDATE SET
  is_enabled = EXCLUDED.is_enabled,
  live_sync_mode = COALESCE(provider_settings.live_sync_mode, EXCLUDED.live_sync_mode);

-- Stable series type definitions. Do not change existing IDs.
INSERT INTO series_type_definition (
  id,
  code,
  unit
)
VALUES
  (1, 'heart_rate', 'bpm'),
  (2, 'resting_heart_rate', 'bpm'),
  (3, 'heart_rate_variability_sdnn', 'ms'),
  (4, 'heart_rate_recovery_one_minute', 'bpm'),
  (5, 'walking_heart_rate_average', 'bpm'),
  (7, 'heart_rate_variability_rmssd', 'ms'),

  (20, 'oxygen_saturation', 'percent'),
  (21, 'blood_glucose', 'mg_dl'),
  (22, 'blood_pressure_systolic', 'mmHg'),
  (23, 'blood_pressure_diastolic', 'mmHg'),
  (24, 'respiratory_rate', 'brpm'),
  (25, 'sleeping_breathing_disturbances', 'count'),
  (26, 'blood_alcohol_content', 'mg_dl'),
  (27, 'peripheral_perfusion_index', 'score'),
  (28, 'forced_vital_capacity', 'liters'),
  (29, 'forced_expiratory_volume_1', 'liters'),
  (30, 'peak_expiratory_flow_rate', 'L/min'),
  (31, 'breathing_disturbance_index', 'score'),

  (40, 'height', 'cm'),
  (41, 'weight', 'kg'),
  (42, 'body_fat_percentage', 'percent'),
  (43, 'body_mass_index', 'kg_m2'),
  (44, 'lean_body_mass', 'kg'),
  (45, 'body_temperature', 'celsius'),
  (46, 'skin_temperature', 'celsius'),
  (47, 'waist_circumference', 'cm'),
  (48, 'body_fat_mass', 'kg'),
  (49, 'skeletal_muscle_mass', 'kg'),
  (50, 'skin_temperature_deviation', 'celsius'),
  (51, 'skin_temperature_trend_deviation', 'celsius'),

  (60, 'vo2_max', 'ml_kg_min'),
  (61, 'six_minute_walk_test_distance', 'meters'),
  (62, 'cardiovascular_age', 'years'),

  (80, 'steps', 'count'),
  (81, 'energy', 'kcal'),
  (82, 'basal_energy', 'kcal'),
  (83, 'stand_time', 'minutes'),
  (84, 'exercise_time', 'minutes'),
  (85, 'physical_effort', 'score'),
  (86, 'flights_climbed', 'count'),
  (87, 'average_met', 'met'),

  (100, 'distance_walking_running', 'meters'),
  (101, 'distance_cycling', 'meters'),
  (102, 'distance_swimming', 'meters'),
  (103, 'distance_downhill_snow_sports', 'meters'),
  (104, 'distance_other', 'meters'),

  (120, 'walking_step_length', 'cm'),
  (121, 'walking_speed', 'm_per_s'),
  (122, 'walking_double_support_percentage', 'percent'),
  (123, 'walking_asymmetry_percentage', 'percent'),
  (124, 'walking_steadiness', 'percent'),
  (125, 'stair_descent_speed', 'm_per_s'),
  (126, 'stair_ascent_speed', 'm_per_s'),

  (140, 'running_power', 'watts'),
  (141, 'running_speed', 'm_per_s'),
  (142, 'running_vertical_oscillation', 'cm'),
  (143, 'running_ground_contact_time', 'ms'),
  (144, 'running_stride_length', 'cm'),
  (145, 'running_vertical_ratio', 'percent'),
  (146, 'running_stance_time_balance', 'percent'),

  (160, 'swimming_stroke_count', 'count'),
  (161, 'underwater_depth', 'meters'),

  (180, 'cadence', 'rpm'),
  (181, 'power', 'watts'),
  (182, 'speed', 'm_per_s'),
  (183, 'workout_effort_score', 'score'),
  (184, 'estimated_workout_effort_score', 'score'),

  (200, 'environmental_audio_exposure', 'dB'),
  (201, 'headphone_audio_exposure', 'dB'),
  (202, 'environmental_sound_reduction', 'dB'),
  (203, 'time_in_daylight', 'minutes'),
  (204, 'water_temperature', 'celsius'),
  (205, 'uv_exposure', 'count'),
  (206, 'inhaler_usage', 'count'),
  (207, 'weather_temperature', 'celsius'),
  (208, 'weather_humidity', 'percent'),
  (209, 'elevation', 'meters'),
  (210, 'latitude', 'degrees'),
  (211, 'longitude', 'degrees'),
  (212, 'air_temperature', 'celsius'),

  (220, 'garmin_stress_level', 'score'),
  (221, 'garmin_skin_temperature', 'celsius'),
  (222, 'garmin_fitness_age', 'years'),
  (223, 'garmin_body_battery', 'percent'),

  (500, 'electrodermal_activity', 'count'),
  (501, 'push_count', 'count'),
  (502, 'atrial_fibrillation_burden', 'count'),
  (503, 'insulin_delivery', 'count'),
  (504, 'number_of_times_fallen', 'count'),
  (505, 'number_of_alcoholic_beverages', 'count'),
  (506, 'nike_fuel', 'count'),
  (507, 'hydration', 'mL')
ON CONFLICT (id) DO UPDATE SET
  code = EXCLUDED.code,
  unit = EXCLUDED.unit;

-- Keep identity sequence ahead of explicit stable IDs.
SELECT setval(
  pg_get_serial_sequence('series_type_definition', 'id'),
  (SELECT max(id) FROM series_type_definition)
);
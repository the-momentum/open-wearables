-- Unified event records such as workouts, sleep sessions, and menstrual cycle events.
CREATE TABLE event_record (
  -- Primary event record identifier.
  id UUID PRIMARY KEY,

  -- Provider-side external identifier.
  external_id VARCHAR(100),

  -- Data source this event belongs to.
  data_source_id UUID NOT NULL REFERENCES data_source (id) ON DELETE CASCADE,

  -- Event category such as workout, sleep, or menstrual_cycle.
  category VARCHAR(32) NOT NULL,

  -- Provider-specific event type.
  type VARCHAR(32),

  -- Source name reported by the provider.
  source_name VARCHAR(64) NOT NULL,

  -- Event duration in seconds.
  duration_seconds INTEGER,

  -- Event start timestamp.
  start_datetime TIMESTAMPTZ NOT NULL,

  -- Event end timestamp.
  end_datetime TIMESTAMPTZ NOT NULL,

  -- Timezone offset from the original data source.
  zone_offset VARCHAR(10),

  -- Timestamp when this event was created.
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Base detail record for category-specific event detail tables.
CREATE TABLE event_record_detail (
  -- Event record this detail belongs to.
  record_id UUID PRIMARY KEY REFERENCES event_record (id) ON DELETE CASCADE,

  -- Detail type such as workout, sleep, or menstrual_cycle.
  detail_type VARCHAR(32) NOT NULL,

  -- Timestamp when this detail was created.
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Workout-specific event details.
CREATE TABLE workout_details (
  -- Event detail record identifier.
  record_id UUID PRIMARY KEY REFERENCES event_record_detail (record_id) ON DELETE CASCADE,

  -- Minimum heart rate during workout.
  heart_rate_min INTEGER,

  -- Maximum heart rate during workout.
  heart_rate_max INTEGER,

  -- Average heart rate during workout.
  heart_rate_avg NUMERIC(5, 2),

  -- Energy burned during workout.
  energy_burned NUMERIC(10, 3),

  -- Workout distance.
  distance NUMERIC(10, 3),

  -- Step count during workout.
  steps_count INTEGER,

  -- Maximum speed.
  max_speed NUMERIC(5, 2),

  -- Maximum power in watts.
  max_watts NUMERIC(10, 3),

  -- Moving time in seconds.
  moving_time_seconds INTEGER,

  -- Total elevation gain.
  total_elevation_gain NUMERIC(10, 3),

  -- Average speed.
  average_speed NUMERIC(5, 2),

  -- Average cadence.
  average_cadence NUMERIC(5, 2),

  -- Average power in watts.
  average_watts NUMERIC(10, 3),

  -- Highest elevation.
  elev_high NUMERIC(10, 3),

  -- Lowest elevation.
  elev_low NUMERIC(10, 3),

  -- Workout segments from provider payload.
  segments JSONB,

  -- Heart-rate zones from provider payload.
  hr_zones JSONB,

  -- Power zones from provider payload.
  power_zones JSONB
);

-- Sleep-specific event details.
CREATE TABLE sleep_details (
  -- Event detail record identifier.
  record_id UUID PRIMARY KEY REFERENCES event_record_detail (record_id) ON DELETE CASCADE,

  -- Total sleep duration in minutes.
  sleep_total_duration_minutes INTEGER,

  -- Total time in bed in minutes.
  sleep_time_in_bed_minutes INTEGER,

  -- Sleep efficiency score.
  sleep_efficiency_score NUMERIC(5, 2),

  -- Deep sleep duration in minutes.
  sleep_deep_minutes INTEGER,

  -- REM sleep duration in minutes.
  sleep_rem_minutes INTEGER,

  -- Light sleep duration in minutes.
  sleep_light_minutes INTEGER,

  -- Awake duration in minutes.
  sleep_awake_minutes INTEGER,

  -- Whether this sleep event is a nap.
  is_nap BOOLEAN,

  -- Provider sleep stages payload.
  sleep_stages JSONB
);

-- Menstrual-cycle-specific event details.
CREATE TABLE menstrual_cycle_details (
  -- Event detail record identifier.
  record_id UUID PRIMARY KEY REFERENCES event_record_detail (record_id) ON DELETE CASCADE,

  -- Day number in the current cycle.
  day_in_cycle INTEGER,

  -- Current phase identifier.
  current_phase INTEGER,

  -- Current phase name/type.
  current_phase_type VARCHAR(32),

  -- Length of the current phase in days.
  length_of_current_phase INTEGER,

  -- Number of days until next phase.
  days_until_next_phase INTEGER,

  -- Predicted full cycle length.
  predicted_cycle_length INTEGER,

  -- Whether this cycle is predicted.
  is_predicted_cycle BOOLEAN,

  -- Actual cycle length.
  cycle_length INTEGER,

  -- Timestamp when cycle data was last updated.
  last_updated_at TIMESTAMPTZ,

  -- Whether user specified cycle length.
  has_specified_cycle_length BOOLEAN,

  -- Whether user specified period length.
  has_specified_period_length BOOLEAN,

  -- Period length in days.
  period_length INTEGER,

  -- Fertile window start day.
  fertile_window_start INTEGER,

  -- Length of fertile window in days.
  length_of_fertile_window INTEGER,

  -- Provider pregnancy snapshot payload.
  pregnancy_snapshot JSONB
);

-- Lookup index for events by source and category.
CREATE INDEX ix_event_record_source_category
  ON event_record (data_source_id, category);

-- Unique event identity by source and time range.
CREATE UNIQUE INDEX ix_event_record_source_time
  ON event_record (data_source_id, start_datetime, end_datetime);

-- JSONB lookup index for workout segments.
CREATE INDEX ix_workout_details_segments_gin
  ON workout_details USING gin (segments jsonb_path_ops);

-- JSONB lookup index for workout heart-rate zones.
CREATE INDEX ix_workout_details_hr_zones_gin
  ON workout_details USING gin (hr_zones jsonb_path_ops);

-- JSONB lookup index for workout power zones.
CREATE INDEX ix_workout_details_power_zones_gin
  ON workout_details USING gin (power_zones jsonb_path_ops);

-- JSONB lookup index for sleep stages.
CREATE INDEX ix_sleep_details_stages_gin
  ON sleep_details USING gin (sleep_stages jsonb_path_ops);
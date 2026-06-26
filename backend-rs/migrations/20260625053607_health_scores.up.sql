-- Normalized health scores from providers or internal scoring logic.
CREATE TABLE health_score (
  -- Primary health score identifier.
  id UUID PRIMARY KEY,

  -- User this health score belongs to.
  user_id UUID NOT NULL REFERENCES "user" (id) ON DELETE CASCADE,

  -- Data source linked to this score.
  data_source_id UUID REFERENCES data_source (id) ON DELETE CASCADE,

  -- Provider that produced this score.
  provider VARCHAR(50) NOT NULL,

  -- Score category such as sleep, recovery, readiness, activity, or stress.
  category VARCHAR(32) NOT NULL,

  -- Numeric score value.
  value NUMERIC(6, 3),

  -- Qualifier label from provider or scoring engine.
  qualifier VARCHAR(32),

  -- Timestamp this score represents.
  recorded_at TIMESTAMPTZ NOT NULL,

  -- Timezone offset from the original data source.
  zone_offset VARCHAR(10),

  -- Score component breakdown.
  components JSONB,

  -- Optional sleep event linked to this score.
  sleep_record_id UUID REFERENCES event_record (id) ON DELETE CASCADE,

  -- Timestamp when this health score was created.
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT uq_health_score_user_provider_category_time UNIQUE (
    user_id,
    provider,
    category,
    recorded_at
  )
);

-- Unique score linked to one sleep record.
CREATE UNIQUE INDEX uq_health_score_sleep_record
  ON health_score (sleep_record_id)
  WHERE sleep_record_id IS NOT NULL;
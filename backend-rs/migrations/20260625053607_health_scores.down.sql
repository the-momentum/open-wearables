-- Add down migration script here
-- Drop indexes first.
DROP INDEX IF EXISTS uq_health_score_sleep_record;

-- Drop health score tables.
DROP TABLE IF EXISTS health_score;
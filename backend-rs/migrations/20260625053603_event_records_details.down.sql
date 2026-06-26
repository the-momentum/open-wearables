-- Drop indexes first.
DROP INDEX IF EXISTS ix_sleep_details_stages_gin;
DROP INDEX IF EXISTS ix_workout_details_power_zones_gin;
DROP INDEX IF EXISTS ix_workout_details_hr_zones_gin;
DROP INDEX IF EXISTS ix_workout_details_segments_gin;
DROP INDEX IF EXISTS ix_event_record_source_time;
DROP INDEX IF EXISTS ix_event_record_source_category;

-- Drop category-specific event detail tables.
DROP TABLE IF EXISTS menstrual_cycle_details;
DROP TABLE IF EXISTS sleep_details;
DROP TABLE IF EXISTS workout_details;

-- Drop base event detail tables.
DROP TABLE IF EXISTS event_record_detail;
DROP TABLE IF EXISTS event_record;
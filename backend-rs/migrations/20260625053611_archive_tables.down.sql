-- Drop indexes first.
DROP INDEX IF EXISTS ix_data_point_series_archive_bucket_start_at;
DROP INDEX IF EXISTS ix_provider_priority_priority;
DROP INDEX IF EXISTS ix_device_type_priority_priority;

-- Drop archive and settings tables.
DROP TABLE IF EXISTS data_point_series_archive;
DROP TABLE IF EXISTS provider_priority;
DROP TABLE IF EXISTS device_type_priority;
DROP TABLE IF EXISTS archival_settings;

-- Drop custom enum types.
DROP TYPE IF EXISTS devicetype;
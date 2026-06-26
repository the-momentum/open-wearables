-- Drop indexes first.
DROP INDEX IF EXISTS uq_data_source_identity;
DROP INDEX IF EXISTS ix_data_source_user_provider;

-- Drop time-series tables.
DROP TABLE IF EXISTS data_point_series;
DROP TABLE IF EXISTS data_source;
DROP TABLE IF EXISTS series_type_definition;
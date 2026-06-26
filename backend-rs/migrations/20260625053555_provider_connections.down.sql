-- Drop indexes first.
DROP INDEX IF EXISTS ix_user_connection_provider_external_id;
DROP INDEX IF EXISTS ix_user_connection_status_user_id;
DROP INDEX IF EXISTS ix_user_connection_token_expiry;
DROP INDEX IF EXISTS ix_user_connection_user_provider;

-- Drop provider connection tables.
DROP TABLE IF EXISTS user_connection;
DROP TABLE IF EXISTS provider_settings;
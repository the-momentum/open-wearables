-- Drop indexes first.
DROP INDEX IF EXISTS ix_user_invitation_code_user_id;
DROP INDEX IF EXISTS ix_refresh_token_developer_id;
DROP INDEX IF EXISTS ix_refresh_token_user_id;

-- Drop dependent identity/auth tables.
DROP TABLE IF EXISTS user_invitation_code;
DROP TABLE IF EXISTS refresh_token;
DROP TABLE IF EXISTS personal_record;
DROP TABLE IF EXISTS invitation;
DROP TABLE IF EXISTS application;
DROP TABLE IF EXISTS api_key;

-- Drop root identity tables.
DROP TABLE IF EXISTS "user";
DROP TABLE IF EXISTS developer;
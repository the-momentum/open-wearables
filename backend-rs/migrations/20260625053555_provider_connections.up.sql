-- Provider-level configuration such as enabled state, live sync mode, and webhook secret.
CREATE TABLE provider_settings (
  -- Provider name.
  provider VARCHAR(64) PRIMARY KEY,

  -- Whether this provider is enabled.
  is_enabled BOOLEAN NOT NULL,

  -- Live sync mode for this provider.
  live_sync_mode VARCHAR(32),

  -- Provider webhook secret.
  webhook_secret TEXT,

  -- Timestamp when this provider setting was created.
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- OAuth connection between a user and an external provider.
CREATE TABLE user_connection (
  -- Primary user connection identifier.
  id UUID PRIMARY KEY,

  -- User who owns this provider connection.
  user_id UUID NOT NULL REFERENCES "user" (id) ON DELETE CASCADE,

  -- Provider name.
  provider VARCHAR(64) NOT NULL,

  -- Provider-side user identifier.
  provider_user_id TEXT,

  -- Provider-side username.
  provider_username TEXT,

  -- Provider access token.
  access_token TEXT,

  -- Provider refresh token.
  refresh_token TEXT,

  -- Timestamp when provider token expires.
  token_expires_at TIMESTAMPTZ,

  -- Provider OAuth scope.
  scope TEXT,

  -- Connection status.
  status VARCHAR(64) NOT NULL,

  -- Timestamp when this connection was last synced.
  last_synced_at TIMESTAMPTZ,

  -- Timestamp when this connection was created.
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  -- Timestamp when this connection was last updated.
  updated_at TIMESTAMPTZ NOT NULL
);

-- Unique provider connection per user/provider.
CREATE UNIQUE INDEX ix_user_connection_user_provider
  ON user_connection (user_id, provider);

-- Lookup index for active token expiry.
CREATE INDEX ix_user_connection_token_expiry
  ON user_connection (token_expires_at)
  WHERE status = 'active';

-- Lookup index for connection status by user.
CREATE INDEX ix_user_connection_status_user_id
  ON user_connection (status, user_id);

-- Lookup index for provider external user id.
CREATE INDEX ix_user_connection_provider_external_id
  ON user_connection (provider, provider_user_id)
  WHERE provider_user_id IS NOT NULL AND status = 'active';
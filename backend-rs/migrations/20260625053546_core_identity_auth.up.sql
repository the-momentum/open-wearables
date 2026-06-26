-- Admin/developer account for dashboard and portal access.
CREATE TABLE developer (
  -- Primary developer identifier.
  id UUID PRIMARY KEY,

  -- Timestamp when this developer was created.
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  -- Timestamp when this developer was last updated.
  updated_at TIMESTAMPTZ NOT NULL,

  -- Developer first name.
  first_name VARCHAR(100),

  -- Developer last name.
  last_name VARCHAR(100),

  -- Unique developer email address.
  email VARCHAR(255) NOT NULL UNIQUE,

  -- Hashed developer password.
  hashed_password VARCHAR(255) NOT NULL
);

-- Data owner account.
CREATE TABLE "user" (
  -- Primary user identifier.
  id UUID PRIMARY KEY,

  -- Timestamp when this user was created.
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  -- User first name.
  first_name VARCHAR(100),

  -- User last name.
  last_name VARCHAR(100),

  -- User email address.
  email VARCHAR,

  -- External user identifier from the application/customer system.
  external_user_id VARCHAR(255) UNIQUE
);

-- Global API key for external service access.
CREATE TABLE api_key (
  -- Actual API key value.
  id VARCHAR(64) PRIMARY KEY,

  -- Human-readable API key name.
  name TEXT NOT NULL,

  -- Developer who created this API key.
  created_by UUID REFERENCES developer (id) ON DELETE SET NULL,

  -- Timestamp when this API key was created.
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- SDK application for external mobile apps.
CREATE TABLE application (
  -- Primary application identifier.
  id UUID PRIMARY KEY,

  -- Public application identifier used by SDK clients.
  app_id VARCHAR(64) NOT NULL UNIQUE,

  -- Hashed application secret.
  app_secret_hash TEXT NOT NULL,

  -- Display name of the application.
  name VARCHAR(100) NOT NULL,

  -- Developer who owns this application.
  developer_id UUID REFERENCES developer (id) ON DELETE SET NULL,

  -- Timestamp when this application was created.
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  -- Timestamp when this application was last updated.
  updated_at TIMESTAMPTZ NOT NULL
);

-- Developer invitation for dashboard/admin onboarding.
CREATE TABLE invitation (
  -- Primary invitation identifier.
  id UUID PRIMARY KEY,

  -- Invited email address.
  email VARCHAR(255) NOT NULL,

  -- Unique invitation token.
  token VARCHAR(255) NOT NULL UNIQUE,

  -- Invitation status.
  status VARCHAR(50) NOT NULL,

  -- Timestamp when this invitation expires.
  expires_at TIMESTAMPTZ NOT NULL,

  -- Developer who created this invitation.
  invited_by_id UUID REFERENCES developer (id) ON DELETE SET NULL,

  -- Timestamp when this invitation was created.
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Slow-changing physical attributes linked to a user.
CREATE TABLE personal_record (
  -- Primary personal record identifier.
  id UUID PRIMARY KEY,

  -- User this personal record belongs to.
  user_id UUID NOT NULL UNIQUE REFERENCES "user" (id) ON DELETE CASCADE,

  -- User birth date.
  birth_date DATE,

  -- Biological sex flag from the original model.
  sex BOOLEAN,

  -- Gender value.
  gender VARCHAR(32),

  -- Timestamp when this personal record was created.
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Refresh tokens for SDK users and developers.
CREATE TABLE refresh_token (
  -- Opaque refresh token identifier.
  id VARCHAR(64) PRIMARY KEY,

  -- Token type.
  token_type VARCHAR(64) NOT NULL,

  -- SDK user linked to this refresh token.
  user_id UUID REFERENCES "user" (id) ON DELETE CASCADE,

  -- SDK application identifier.
  app_id VARCHAR(64),

  -- Developer linked to this refresh token.
  developer_id UUID REFERENCES developer (id) ON DELETE SET NULL,

  -- Timestamp when this token was last used.
  last_used_at TIMESTAMPTZ,

  -- Timestamp when this token was revoked.
  revoked_at TIMESTAMPTZ,

  -- Timestamp when this refresh token was created.
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Single-use invitation code for SDK user onboarding.
CREATE TABLE user_invitation_code (
  -- Primary invitation code identifier.
  id UUID PRIMARY KEY,

  -- Short invitation code entered by the mobile user.
  code VARCHAR(10) NOT NULL UNIQUE,

  -- User this invitation code is for.
  user_id UUID NOT NULL REFERENCES "user" (id) ON DELETE CASCADE,

  -- Developer who created this invitation code.
  created_by_id UUID REFERENCES developer (id) ON DELETE SET NULL,

  -- Timestamp when this code expires.
  expires_at TIMESTAMPTZ NOT NULL,

  -- Timestamp when this code was redeemed.
  redeemed_at TIMESTAMPTZ,

  -- Timestamp when this code was revoked.
  revoked_at TIMESTAMPTZ,

  -- Timestamp when this code was created.
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Lookup index for refresh tokens by user.
CREATE INDEX ix_refresh_token_user_id
  ON refresh_token (user_id);

-- Lookup index for refresh tokens by developer.
CREATE INDEX ix_refresh_token_developer_id
  ON refresh_token (developer_id);

-- Lookup index for invitation codes by user.
CREATE INDEX ix_user_invitation_code_user_id
  ON user_invitation_code (user_id);
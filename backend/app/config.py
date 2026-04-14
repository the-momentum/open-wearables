from __future__ import annotations

import warnings
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.schemas.enums import ProviderName

from pydantic import AnyHttpUrl, Field, SecretStr, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.utils.config_utils import (
    EncryptedField,
    EnvironmentType,
    FernetDecryptorField,
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent / "config" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        # default env_file solution search .env every time BaseSettings is instantiated
        # dotenv search .env when module is imported, without usecwd it starts from the file it was called
    )

    # CORE SETTINGS
    fernet_decryptor: FernetDecryptorField = Field(FernetDecryptorField("MASTER_KEY"))
    environment: EnvironmentType = EnvironmentType.LOCAL

    # API SETTINGS
    api_name: str = "Open Wearables API"
    api_v1: str = "/api/v1"
    api_latest: str = api_v1
    paging_limit: int = 100
    cors_origins: list[AnyHttpUrl] = []
    cors_allow_all: bool = False

    # DATABASE SETTINGS
    db_host: str = "db"
    db_port: int = 5432
    db_name: str = "open-wearables"
    db_user: str = "open-wearables"
    db_password: SecretStr = SecretStr("open-wearables")

    # Sentry
    SENTRY_ENABLED: bool = False
    SENTRY_DSN: str | None = None
    SENTRY_SAMPLES_RATE: float = 0.5
    SENTRY_ENV: str | None = None
    SENTRY_SERVER_NAME: str | None = None

    # AUTH SETTINGS
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    token_lifetime: int = 3600

    # VALIDATION SETTINGS
    min_password_length: int = 8

    # REDIS SETTINGS
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: SecretStr | None = None
    redis_username: str | None = None  # Redis 6.0+ ACL

    # ADMIN ACCOUNT SEED
    admin_email: str = "admin@admin.com"
    admin_password: SecretStr = SecretStr("your-secure-password")

    # Time to live for sleep state in Redis
    redis_sleep_ttl_seconds: int = 24 * 3600  # 24 hours

    # Time between sleep phases to conclude end of sleep session
    sleep_end_gap_minutes: int = 120  # 2 hours

    # SYNC SETTINGS
    sync_interval_seconds: int = 3600  # Default: 1 hour (3600 seconds)
    sleep_sync_interval_seconds: int = 3600  # Default: 1 hour (3600 seconds)

    # SCORE SETTINGS
    score_backfill_days: int = 30  # How far back the missing-score query looks
    sleep_score_interval_seconds: int = 600  # How often to run the fill-missing-scores task (default: 10 min)

    # API SETTINGS
    api_base_url: str = "http://localhost:8000"

    # SUUNTO OAUTH SETTINGS
    suunto_client_id: str | None = None
    suunto_client_secret: SecretStr | None = None
    suunto_redirect_uri: str | None = None  # Deprecated: use API_BASE_URL
    suunto_subscription_key: SecretStr | None = None
    suunto_default_scope: str = ""

    # GARMIN OAUTH SETTINGS
    garmin_client_id: str | None = None
    garmin_client_secret: SecretStr | None = None
    garmin_redirect_uri: str | None = None  # Deprecated: use API_BASE_URL
    garmin_default_scope: str = ""  # Scope is managed at app creation in Garmin Developer Portal

    # POLAR OAUTH SETTINGS
    polar_client_id: str | None = None
    polar_client_secret: SecretStr | None = None
    polar_redirect_uri: str | None = None  # Deprecated: use API_BASE_URL
    polar_default_scope: str = "accesslink.read_all"

    # WHOOP OAUTH SETTINGS
    whoop_client_id: str | None = None
    whoop_client_secret: SecretStr | None = None
    whoop_redirect_uri: str | None = None  # Deprecated: use API_BASE_URL
    whoop_default_scope: str = "offline read:cycles read:sleep read:recovery read:workout"

    # FITBIT OAUTH SETTINGS
    fitbit_client_id: str | None = None
    fitbit_client_secret: SecretStr | None = None
    fitbit_redirect_uri: str | None = None  # Deprecated: use API_BASE_URL
    fitbit_default_scope: str = "activity heartrate sleep profile"

    # OURA OAUTH SETTINGS
    oura_client_id: str | None = None
    oura_client_secret: SecretStr | None = None
    oura_redirect_uri: str | None = None  # Deprecated: use API_BASE_URL
    oura_default_scope: str = "personal daily activity heartrate workout session spo2 ring_configuration heart_health"
    oura_webhook_verification_token: SecretStr | None = None

    # STRAVA OAUTH SETTINGS
    strava_client_id: str | None = None
    strava_client_secret: SecretStr | None = None
    strava_redirect_uri: str | None = None  # Deprecated: use API_BASE_URL
    strava_default_scope: str = "activity:read_all,profile:read_all"
    strava_webhook_verify_token: str = "open-wearables-strava-verify"
    # Strava API max is 200 activities per page
    strava_events_per_page: int = 200

    # ULTRAHUMAN OAUTH SETTINGS
    ultrahuman_client_id: str | None = None
    ultrahuman_client_secret: SecretStr | None = None
    ultrahuman_redirect_uri: str | None = None  # Deprecated: use API_BASE_URL
    ultrahuman_default_scope: str = "ring_data cgm_data profile"

    # EMAIL SETTINGS (Resend)
    resend_api_key: SecretStr | None = None
    email_from_address: str | None = None
    email_from_name: str = "Open Wearables"
    frontend_url: str = "http://localhost:3000"
    invitation_expire_days: int = 7
    email_max_retries: int = 5

    # SDK INVITATION CODE SETTINGS
    user_invitation_code_expire_days: int = 7

    # AWS SETTINGS
    aws_bucket_name: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: SecretStr | None = None
    aws_region: str = "eu-north-1"
    # for topic ARN verification from SNS notification (signature is verified regardless)
    aws_sns_topic_arn: SecretStr | None = None

    xml_chunk_size: int = 50_000

    # RAW PAYLOAD STORAGE
    raw_payload_storage: str = "disabled"  # disabled | log | s3
    raw_payload_max_size_bytes: int = 10 * 1024 * 1024  # 10 MB
    raw_payload_s3_bucket: str | None = None  # defaults to aws_bucket_name if not set
    raw_payload_s3_prefix: str = "raw-payloads"
    raw_payload_s3_endpoint_url: str | None = None  # for S3-compatible storage (e.g. Railway Object Storage)

    # SVIX WEBHOOK SETTINGS
    svix_server_url: str = "http://svix-server:8071"
    # Signing secret used by the Svix server to verify JWTs.  Must match SVIX_JWT_SECRET in docker-compose.
    svix_jwt_secret: SecretStr | None = None
    # Bearer token for the Svix API.  If unset, auto-generated from svix_jwt_secret at startup.
    svix_auth_token: SecretStr | None = None

    @field_validator("cors_origins", mode="after")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str] | str:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        if isinstance(v, (list, str)):
            return v

        # This should never be reached given the type annotation, but ensures type safety
        raise ValueError(f"Unexpected type for cors_origins: {type(v)}")

    def oauth_redirect_uri(self, provider: ProviderName) -> str:
        """Build OAuth redirect URI for a provider.

        Uses the legacy per-provider *_REDIRECT_URI env var if set,
        otherwise builds the URI from API_BASE_URL.
        """
        legacy_attr = f"{provider.value}_redirect_uri"
        legacy_value = getattr(self, legacy_attr, None)
        if legacy_value is not None:
            warnings.warn(
                f"{legacy_attr.upper()} is deprecated, use API_BASE_URL instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return legacy_value
        return f"{self.api_base_url}/api/v1/oauth/{provider.value}/callback"

    @property
    def redis_url(self) -> str:
        """Get Redis connection URL built from individual settings."""
        auth_part = ""
        if self.redis_username and self.redis_password:
            auth_part = f"{self.redis_username}:{self.redis_password.get_secret_value()}@"
        elif self.redis_password:
            auth_part = f":{self.redis_password.get_secret_value()}@"
        elif self.redis_username:
            auth_part = f"{self.redis_username}@"

        return f"redis://{auth_part}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # Decryptor for encrypted fields
    @field_validator("*", mode="after")
    @classmethod
    def _decryptor(cls, v: Any, validation_info: ValidationInfo, *args, **kwargs) -> Any:
        if isinstance(v, EncryptedField):
            return v.get_decrypted_value(validation_info.data["fernet_decryptor"])
        return v

    @property
    def db_uri(self) -> str:
        return (
            f"postgresql+psycopg://"
            f"{self.db_user}:{self.db_password.get_secret_value()}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    # 0. pytest ini_options
    # 1. environment variables
    # 2. .env
    # 3. default values in pydantic settings


@lru_cache()
def _get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = _get_settings()

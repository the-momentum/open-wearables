from functools import lru_cache
from pathlib import Path
from typing import Any

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
    fernet_decryptor: FernetDecryptorField = Field("MASTER_KEY")
    environment: EnvironmentType = EnvironmentType.LOCAL

    # API SETTINGS
    api_name: str = "Open Wearables API"
    api_v1: str = "/api/v1"
    api_latest: str = api_v1
    paging_limit: int = 100
    cors_origins: list[AnyHttpUrl] = []
    cors_allow_all: bool = False

    # DATABASE SETTINGS
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "open-wearables"
    db_user: str = "open-wearables"
    db_password: SecretStr = SecretStr("open-wearables")

    # CELERY SETTINGS
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    # Sentry
    SENTRY_ENABLED: bool = False
    SENTRY_DSN: str | None = None
    SENTRY_SAMPLES_RATE: float = 0.5
    SENTRY_ENV: str | None = None

    # AUTH0 SETTINGS (deprecated, will be removed)
    auth0_domain: str = ""
    auth0_audience: str = ""
    auth0_issuer: str = ""
    auth0_algorithms: list[str] = ["RS256"]

    # AUTH SETTINGS
    secret_key: str
    token_lifetime: int = 3600

    # REDIS SETTINGS
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    # SUUNTO OAUTH SETTINGS
    suunto_client_id: str | None = None
    suunto_client_secret: SecretStr | None = None
    suunto_redirect_uri: str = "http://localhost:8000/api/v1/oauth/suunto/callback"
    suunto_subscription_key: SecretStr
    suunto_authorize_url: str = "https://cloudapi-oauth.suunto.com/oauth/authorize"
    suunto_token_url: str = "https://cloudapi-oauth.suunto.com/oauth/token"
    suunto_api_base_url: str = "https://cloudapi.suunto.com"
    suunto_default_scope: str = "workout"

    # GARMIN OAUTH SETTINGS (for future use)
    garmin_client_id: str | None = None
    garmin_client_secret: SecretStr | None = None
    garmin_redirect_uri: str = "http://localhost:8000/api/v1/oauth/garmin/callback"
    garmin_consumer_key: str | None = None
    garmin_authorize_url: str = "https://connect.garmin.com/oauthConfirm"
    garmin_token_url: str = "https://connectapi.garmin.com/oauth-service/oauth/access_token"
    garmin_api_base_url: str = "https://apis.garmin.com"
    garmin_default_scope: str = "activity:read"

    # POLAR OAUTH SETTINGS
    polar_client_id: str | None = None
    polar_client_secret: SecretStr | None = None
    polar_redirect_uri: str = "http://localhost:8000/api/v1/oauth/polar/callback"
    polar_authorize_url: str = "https://flow.polar.com/oauth2/authorization"
    polar_token_url: str = "https://polarremote.com/v2/oauth2/token"
    polar_api_base_url: str = "https://www.polaraccesslink.com"
    polar_default_scope: str = "accesslink.read_all"

    @field_validator("cors_origins", mode="after")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str] | str:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        if isinstance(v, (list, str)):
            return v

        # This should never be reached given the type annotation, but ensures type safety
        raise ValueError(f"Unexpected type for cors_origins: {type(v)}")

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

    @property
    def auth0_issuer_url(self) -> str:
        return f"https://{self.auth0_domain}/"

    # 0. pytest ini_options
    # 1. environment variables
    # 2. .env
    # 3. default values in pydantic settings


@lru_cache()
def _get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = _get_settings()

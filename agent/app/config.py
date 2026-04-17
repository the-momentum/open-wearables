from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any, ClassVar

from pydantic import AnyHttpUrl, Field, SecretStr, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.utils.config_utils import (
    EncryptedField,
    EnvironmentType,
    FernetDecryptorField,
)


class LLMProvider(StrEnum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    # SELF_HOSTED = "self_hosted"  # TBD


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
    api_name: str = "Open Wearables Agent API"
    api_v1: str = "/api/v1"
    api_latest: str = api_v1
    paging_limit: int = 100
    cors_origins: list[AnyHttpUrl] = []
    cors_allow_all: bool = False

    # DATABASE SETTINGS
    db_host: str = "db"
    db_port: int = 5432
    db_name: str = "agent"
    db_user: str = "open-wearables"
    db_password: SecretStr = SecretStr("open-wearables")

    # CELERY SETTINGS
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    # JWT SETTINGS
    secret_key: str
    algorithm: str = "HS256"

    # Sentry
    SENTRY_ENABLED: bool = False
    SENTRY_DSN: str | None = None
    SENTRY_SAMPLES_RATE: float = 0.5
    SENTRY_ENV: str | None = None

    # LLM provider (anthropic | openai | google) — must have matching API key set
    llm_provider: LLMProvider = LLMProvider.ANTHROPIC
    llm_model: str | None = None
    llm_model_workers: str | None = None
    anthropic_api_key: SecretStr = SecretStr("")
    openai_api_key: SecretStr = SecretStr("")
    google_api_key: SecretStr = SecretStr("")

    # OW Backend integration
    ow_api_url: str = "http://app:8000"
    ow_api_key: SecretStr = SecretStr("")

    # Conversation lifecycle
    session_timeout_minutes: int = 10
    conversation_close_hours: int = 24
    history_summary_threshold: int = 20
    max_tool_calls: int = 10

    # Agent tuning
    guardrails_soft_word_limit: int = 150
    router_context_turns: int = 3

    # OW backend client
    ow_api_timeout: int = 30

    _PROVIDER_DEFAULTS: ClassVar[dict[LLMProvider, dict[str, str]]] = {
        LLMProvider.ANTHROPIC: {
            "llm_model": "claude-sonnet-4-6",
            "llm_model_workers": "claude-haiku-4-5-20251001",
        },
        LLMProvider.OPENAI: {
            "llm_model": "gpt-5",
            "llm_model_workers": "gpt-5-mini",
        },
        LLMProvider.GOOGLE: {
            "llm_model": "gemini-2.0-flash",
            "llm_model_workers": "gemini-2.0-flash-lite",
        },
    }

    @model_validator(mode="after")
    def _set_model_defaults(self) -> "Settings":
        defaults = self._PROVIDER_DEFAULTS.get(self.llm_provider, self._PROVIDER_DEFAULTS[LLMProvider.ANTHROPIC])
        if not self.llm_model:
            self.llm_model = defaults["llm_model"]
        if not self.llm_model_workers:
            self.llm_model_workers = defaults["llm_model_workers"]
        return self

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
    def db_uri_async(self) -> str:
        return self.db_uri

    # 0. pytest ini_options
    # 1. environment variables
    # 2. .env
    # 3. default values in pydantic settings


@lru_cache()
def _get_settings() -> Settings:
    return Settings()  # type: ignore


settings = _get_settings()

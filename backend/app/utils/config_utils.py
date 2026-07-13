import os
import re
from datetime import timedelta
from enum import Enum
from functools import wraps
from typing import Any, Callable, Generator, Protocol

from cryptography.fernet import Fernet
from pydantic import ValidationInfo

CallableGenerator = Generator[Callable[..., Any], None, None]

_DURATION_RE = re.compile(r"(\d+)([dhm])")
_DURATION_UNIT_SECONDS = {"d": 86400, "h": 3600, "m": 60}


def parse_duration(value: str) -> timedelta:
    """Parse a compact duration string into a timedelta.

    Units: ``d`` (days), ``h`` (hours), ``m`` (minutes). One or more segments,
    e.g. ``"2d"``, ``"20h"``, ``"90m"``, ``"1d12h"``. Raises ``ValueError`` on an
    invalid or empty format.
    """
    cleaned = value.strip().lower()
    matches = _DURATION_RE.findall(cleaned)
    if not matches or _DURATION_RE.sub("", cleaned).strip():
        raise ValueError(f"Invalid duration {value!r}; expected e.g. '2d', '20h', '90m', '1d12h'")
    total_seconds = sum(int(amount) * _DURATION_UNIT_SECONDS[unit] for amount, unit in matches)
    return timedelta(seconds=total_seconds)


def format_duration(value: timedelta) -> str:
    """Render a timedelta as a compact string, omitting zero parts (e.g. '2d', '1d12h', '1h30m')."""
    total_seconds = int(value.total_seconds())
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
    parts = [f"{n}{unit}" for n, unit in ((days, "d"), (hours, "h"), (minutes, "m")) if n]
    return "".join(parts) or "0m"


class EnvironmentType(str, Enum):
    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class Decryptor(Protocol):
    def decrypt(self, value: bytes) -> bytes: ...


class FakeFernet:
    def decrypt(self, value: bytes) -> bytes:
        return value


class EncryptedField(str):
    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema: dict[str, Any]) -> None:
        field_schema.update(type="str", writeOnly=True)

    @classmethod
    def __get_validators__(cls) -> "CallableGenerator":
        yield cls.validate

    @classmethod
    def validate(cls, value: str, _: ValidationInfo) -> "EncryptedField":
        if isinstance(value, cls):
            return value
        return cls(value)

    def __init__(self, value: str):
        self._secret_value = "".join(value.splitlines()).strip().encode("utf-8")
        self.decrypted = False

    def get_decrypted_value(self, decryptor: Decryptor) -> str:
        if not self.decrypted:
            value = decryptor.decrypt(self._secret_value)
            self._secret_value = value
            self.decrypted = True
        return self._secret_value.decode("utf-8")


class FernetDecryptorField(str):
    def __get_pydantic_json_schema__(self, field_schema: dict[str, Any]) -> None:
        field_schema.update(type="str", writeOnly=True)

    @classmethod
    def __get_validators__(cls) -> "CallableGenerator":
        yield cls.validate

    @classmethod
    def validate(cls, value: str, _: ValidationInfo) -> Fernet | FakeFernet:
        master_key = os.environ.get(value)
        if not master_key:
            return FakeFernet()
        return Fernet(os.environ[value])


def set_env_from_settings(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator to set environment variables from settings.
    This decorator is useful for encrypted fields and providers that
    require API keys to be available as environment variables.
    """

    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        settings = func(*args, **kwargs)
        # os.environ["EXAMPLE_API_KEY"] = settings.EXAMPLE_API_KEY
        return settings  # noqa: RET504

    return wrapper

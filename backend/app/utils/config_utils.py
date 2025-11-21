import os
from enum import Enum
from functools import wraps
from typing import Any, Callable, Generator, Protocol

from cryptography.fernet import Fernet
from pydantic import ValidationInfo

CallableGenerator = Generator[Callable[..., Any], None, None]


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
    def validate(cls, value: str, _: ValidationInfo) -> Fernet:
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

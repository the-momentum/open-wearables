import os
from collections.abc import Callable, Generator
from enum import Enum
from typing import Any

from cryptography.fernet import Fernet
from pydantic import ValidationInfo

CallableGenerator = Generator[Callable[..., Any], None, None]


class EnvironmentType(str, Enum):
    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class FakeFernet:
    def decrypt(self, value: bytes) -> bytes:
        return value


Decryptor = Fernet | FakeFernet


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
    def validate(cls, value: str, _: ValidationInfo) -> Decryptor:
        master_key = os.environ.get(value)
        if not master_key:
            return FakeFernet()
        return Fernet(os.environ[value])

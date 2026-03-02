from enum import StrEnum


class TokenType(StrEnum):
    """Type of refresh token."""

    SDK = "sdk"
    DEVELOPER = "developer"

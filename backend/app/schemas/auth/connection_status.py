from enum import StrEnum


class ConnectionStatus(StrEnum):
    """Status of a user connection to a provider."""

    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
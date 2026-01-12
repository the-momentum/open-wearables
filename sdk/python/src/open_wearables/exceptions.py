"""Exceptions for the Open Wearables SDK."""

from __future__ import annotations

from typing import Any


class OpenWearablesError(Exception):
    """Base exception for Open Wearables SDK."""

    def __init__(self, message: str, status_code: int | None = None, response: Any | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response = response


class AuthenticationError(OpenWearablesError):
    """Raised when API key is invalid or missing."""

    pass


class NotFoundError(OpenWearablesError):
    """Raised when a resource is not found."""

    pass


class ValidationError(OpenWearablesError):
    """Raised when request validation fails."""

    pass


class RateLimitError(OpenWearablesError):
    """Raised when rate limit is exceeded."""

    pass


class ServerError(OpenWearablesError):
    """Raised when the server returns a 5xx error."""

    pass

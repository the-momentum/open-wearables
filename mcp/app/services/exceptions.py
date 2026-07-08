"""Exceptions raised by the Open Wearables MCP client.

Mirrors the naming scheme used in `sdk/python/src/open_wearables/exceptions.py`
so callers can reason about API failures without having to string-match on
error messages.
"""


class OpenWearablesError(Exception):
    """Base exception for MCP client errors talking to the Open Wearables API."""


class AuthenticationError(OpenWearablesError):
    """Raised when the API key is rejected (HTTP 401)."""


class NotFoundError(OpenWearablesError):
    """Raised when a requested resource does not exist (HTTP 404)."""


class ConfigurationError(OpenWearablesError):
    """Raised when the client is not configured (e.g. missing API key)."""

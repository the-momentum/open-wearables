"""Withings OAuth token errors."""

from app.utils.exceptions import (
    InvalidInputError,
    ProviderError,
    ProviderRateLimitError,
    ProviderReauthorizationRequiredError,
)

# Token-request statuses caused by invalid request inputs rather than provider faults.
_TOKEN_CLIENT_ERROR_STATUSES = {247, 250, 283, 286, 293, 303, 304, 342}
# Withings' "Authentication failed" family. On refresh these also mean the grant
# is spent; on exchange they usually mean an expired authorization code.
_AUTHENTICATION_FAILED_STATUSES = {100, 101, 102, 200, 401}
_RATE_LIMIT_STATUS = 601


def withings_token_error(
    *,
    task: str,
    withings_status: int | None = None,
    http_status: int | None = None,
    upstream_body: str | None = None,
) -> InvalidInputError | ProviderError | ProviderReauthorizationRequiredError:
    """The error for a failed token request, from the envelope status or the HTTP one.

    On refresh a failed authentication means the grant is spent: the user must reconnect.
    On exchange it, like any other bad input, rejects the code the OAuth callback brought.
    """
    # an envelope status names the failure; without one ProviderError's default names the HTTP status
    detail = f"Withings token error (status={withings_status})" if withings_status is not None else None
    if withings_status == _RATE_LIMIT_STATUS or http_status == 429:
        return ProviderRateLimitError(
            "withings",
            detail,
            upstream_status=http_status,
            upstream_body=upstream_body,
        )
    authentication_failed = withings_status in _AUTHENTICATION_FAILED_STATUSES or http_status in {400, 401}
    if task == "refresh_access_token" and authentication_failed:
        return ProviderReauthorizationRequiredError("withings")
    client_error = withings_status in _TOKEN_CLIENT_ERROR_STATUSES or (http_status is not None and http_status < 500)
    if task == "exchange_token" and (authentication_failed or client_error):
        return InvalidInputError("Failed to exchange authorization code")
    # The token endpoint has no per-user resource, so any refresh Withings refuses (a client status
    # in the envelope, or an HTTP 4xx like 403/404) means our request or integration is wrong:
    # reported, unlike an outage. The user's own state comes as an envelope status, handled above.
    return ProviderError(
        "withings",
        detail,
        upstream_status=http_status,
        upstream_body=upstream_body,
        request_rejected=True if client_error else None,
    )

"""Withings OAuth token errors."""

from fastapi import HTTPException

# Token-request statuses caused by invalid request inputs rather than provider faults.
_TOKEN_CLIENT_ERROR_STATUSES = {247, 250, 283, 286, 293, 303, 304, 342}
# Withings' "Authentication failed" family. On refresh these also mean the grant
# is spent; on exchange they usually mean an expired authorization code.
_AUTHENTICATION_FAILED_STATUSES = {100, 101, 102, 200, 401}
_RATE_LIMIT_STATUS = 601


class WithingsTokenError(HTTPException):
    """Typed token failure preserving provider status and grant finality."""

    def __init__(
        self,
        *,
        task: str,
        withings_status: int | None = None,
        http_status: int | None = None,
        detail: str | None = None,
    ) -> None:
        self.withings_status = withings_status
        self.http_status = http_status
        authentication_failed = withings_status in _AUTHENTICATION_FAILED_STATUSES or http_status in {400, 401}
        self.invalid_grant = task == "refresh_access_token" and authentication_failed
        if withings_status == _RATE_LIMIT_STATUS or http_status == 429:
            status_code = 429
        elif authentication_failed:
            status_code = 401
        elif withings_status in _TOKEN_CLIENT_ERROR_STATUSES or (http_status is not None and http_status < 500):
            status_code = 400
        else:
            status_code = 500
        super().__init__(
            status_code=status_code,
            detail=detail or f"Withings token error (status={withings_status})",
        )

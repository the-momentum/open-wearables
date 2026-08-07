"""Tests for StravaWebhookHandler.verify_signature.

Regression coverage for the Strava webhook signature verification fix:
X-Strava-Signature was previously only checked for a fresh timestamp and the
HMAC-SHA256 digest (``v1``) was never verified, so anyone could forge events
(activity delete / athlete deauthorize) against ``POST /providers/strava/webhooks``.
"""

import hashlib
import hmac
import time
from unittest.mock import MagicMock, patch

from pydantic import SecretStr
from starlette.requests import Request

from app.config import settings
from app.services.providers.strava.webhook_handler import StravaWebhookHandler

SECRET = "test-strava-client-secret"


def _request(headers: dict[str, str]) -> Request:
    scope: dict[str, object] = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "scheme": "http",
        "server": ("testserver", 80),
        "client": ("testclient", 12345),
        "root_path": "",
        "http_version": "1.1",
    }
    return Request(scope)


def _sign(secret: str, body: bytes, timestamp: int) -> str:
    message = f"{timestamp}.".encode() + body
    digest = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def _handler() -> StravaWebhookHandler:
    return StravaWebhookHandler(workouts=MagicMock())


def _verify(
    handler: StravaWebhookHandler,
    body: bytes,
    *,
    secret: str = SECRET,
    timestamp: int | None = None,
    signature: str | None = None,
    header_name: str = "X-Strava-Signature",
) -> bool:
    ts = timestamp if timestamp is not None else int(time.time())
    sig = signature if signature is not None else _sign(secret, body, ts)
    return handler.verify_signature(_request({header_name: sig}), body)


def test_valid_signature_accepted() -> None:
    with patch.object(settings, "strava_client_secret", SecretStr(SECRET)):
        body = b'{"object_type":"activity","aspect_type":"create","object_id":1,"owner_id":2}'
        assert _verify(_handler(), body) is True


def test_missing_secret_rejects() -> None:
    with patch.object(settings, "strava_client_secret", None):
        body = b"{}"
        assert _verify(_handler(), body) is False


def test_missing_header_rejects() -> None:
    with patch.object(settings, "strava_client_secret", SecretStr(SECRET)):
        body = b"{}"
        assert _verify(_handler(), body, header_name="X-Missing-Header") is False


def test_malformed_header_rejects() -> None:
    with patch.object(settings, "strava_client_secret", SecretStr(SECRET)):
        body = b"{}"
        for bad in ("garbage", "t=notanumber,v1=abc", "v1=abc", "t=123"):
            assert _verify(_handler(), body, signature=bad) is False


def test_wrong_digest_rejects() -> None:
    with patch.object(settings, "strava_client_secret", SecretStr(SECRET)):
        body = b"{}"
        ts = int(time.time())
        forged = f"t={ts},v1={'0' * 64}"
        assert _verify(_handler(), body, signature=forged) is False


def test_tampered_body_rejects() -> None:
    """An attacker-modifying the body invalidates the signature for the same t."""
    with patch.object(settings, "strava_client_secret", SecretStr(SECRET)):
        original = b'{"object_type":"activity","aspect_type":"create","object_id":1,"owner_id":2}'
        tampered = b'{"object_type":"athlete","aspect_type":"delete","object_id":1,"owner_id":2}'
        ts = int(time.time())
        request = _request({"X-Strava-Signature": _sign(SECRET, original, ts)})
        assert _handler().verify_signature(request, tampered) is False


def test_stale_timestamp_rejects() -> None:
    with patch.object(settings, "strava_client_secret", SecretStr(SECRET)):
        body = b"{}"
        stale = int(time.time()) - (settings.strava_webhook_signature_tolerance_seconds + 60)
        assert _verify(_handler(), body, timestamp=stale) is False


def test_wrong_secret_rejects() -> None:
    with patch.object(settings, "strava_client_secret", SecretStr("other-secret")):
        body = b"{}"
        assert _verify(_handler(), body) is False

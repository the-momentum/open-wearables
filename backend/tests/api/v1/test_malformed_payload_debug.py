"""DEBUG: verify the dict-endpoint + worker-validation(+Sentry) changes.

- The endpoint now accepts a raw dict, so a malformed record no longer 400s at HTTP
  (it returns 202 and enqueues).
- The worker (import_data_from_request) validates and reports failures via
  log_and_capture_error (Sentry).
"""

import json
import uuid
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.services.apple.healthkit.import_service import import_service
from tests.factories import ApiKeyFactory, UserFactory

VALID_RECORD = {
    "id": "rec-1",
    "type": "HKQuantityTypeIdentifierHeartRate",
    "startDate": "2026-07-16T00:00:00Z",
    "endDate": "2026-07-16T00:00:01Z",
    "value": 60,
    "unit": "bpm",
}


def _payload(records: list) -> dict:
    return {
        "provider": "apple",
        "sdkVersion": "1.0.0",
        "syncTimestamp": "2026-07-16T00:00:00Z",
        "data": {"records": records, "sleep": [], "workouts": []},
    }


@pytest.fixture(autouse=True)
def mock_celery() -> Generator[MagicMock, None, None]:
    with patch("app.api.routes.v1.sdk_sync.process_sdk_upload") as mock:
        mock.delay.return_value = None
        yield mock


def _post(client: TestClient, api_v1_prefix: str, payload: dict):
    user = UserFactory()
    api_key = ApiKeyFactory()
    return client.post(
        f"{api_v1_prefix}/sdk/users/{user.id}/sync/",
        headers={"X-Open-Wearables-API-Key": api_key.id},
        json=payload,
    )


def test_endpoint_accepts_raw_dict(client: TestClient, db: Session, api_v1_prefix: str) -> None:
    """Endpoint no longer schema-validates: valid AND malformed both enqueue (202)."""
    r_valid = _post(client, api_v1_prefix, _payload([VALID_RECORD]))
    print("\nVALID           ->", r_valid.status_code, r_valid.json())

    r_bad = _post(client, api_v1_prefix, _payload([{**VALID_RECORD, "value": None}]))
    print("MALFORMED null  ->", r_bad.status_code, r_bad.json())

    # unsupported provider is still rejected at the endpoint (routing decision)
    r_prov = _post(client, api_v1_prefix, {**_payload([]), "provider": "nope"})
    print("BAD provider    ->", r_prov.status_code, r_prov.json())

    assert r_valid.status_code == 202
    assert r_bad.status_code == 202  # <-- changed: no longer 400 at HTTP
    assert r_prov.status_code == 400


def test_worker_validation_captures_to_sentry(db: Session) -> None:
    """Worker validates the payload and reports failures via log_and_capture_error."""
    raw = _payload([{**VALID_RECORD, "value": None}])  # the poison
    user_id = str(uuid.uuid4())

    with patch("app.services.apple.healthkit.import_service.log_and_capture_error") as cap:
        resp = import_service.import_data_from_request(
            db, json.dumps(raw), "application/json", user_id, batch_id="batch-debug"
        )

    print("\nworker resp     ->", resp.status_code, resp.response)
    print("log_and_capture_error called:", cap.called, "x", cap.call_count)
    if cap.called:
        exc = cap.call_args.args[0]
        extra = cap.call_args.kwargs.get("extra", {})
        print("  captured exc  :", type(exc).__name__)
        print("  error loc     :", (extra.get("errors") or [{}])[0].get("loc"))
        print("  error msg     :", (extra.get("errors") or [{}])[0].get("msg"))

    assert resp.status_code == 400
    assert cap.called
    assert type(cap.call_args.args[0]).__name__ == "ValidationError"

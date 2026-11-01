"""Attribution headers sent by the mobile SDKs.

Unlike the body, headers are readable even when the request body is truncated.
"""

from collections.abc import Mapping
from typing import Any

_SDK_HEADERS = {
    "x-open-wearables-sdk-version": "sdk_version",
    "x-open-wearables-sdk-platform": "sdk_platform",
    "x-request-id": "request_id",
    "x-open-wearables-outbox-item": "outbox_item_id",
    # Whether the app was in the foreground or background when the batch was built,
    # and what started the sync (HealthKit observer, BGTask, app launch, ...).
    "x-open-wearables-app-state": "app_state",
    "x-open-wearables-sync-trigger": "sync_trigger",
    "user-agent": "user_agent",
}

_MAX_VALUE_LENGTH = 256


def _sanitize(value: str) -> str:
    # Control characters would let a client forge log lines in the text log format.
    cleaned = "".join(char for char in value if char.isprintable()).strip()
    return cleaned[:_MAX_VALUE_LENGTH]


def sdk_request_metadata(headers: Mapping[str, str], body_sdk_version: object = None) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    # Older SDK versions send the version only in the body.
    if isinstance(body_sdk_version, str) and (cleaned := _sanitize(body_sdk_version)):
        fields["sdk_version"] = cleaned
    for header, field in _SDK_HEADERS.items():
        value = headers.get(header)
        if value and (cleaned := _sanitize(value)):
            fields[field] = cleaned
    return fields

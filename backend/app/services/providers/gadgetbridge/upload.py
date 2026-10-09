"""Resumable delivery; an HTTP 202 never marks a batch as successfully imported."""

import json
import os
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from app.services.providers.gadgetbridge.export import SDK_VERSION, fingerprint


def write_private_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def wait_for_batch(
    client: httpx.Client, user_id: str, session_id: str, data: dict[str, Any], timeout: float
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    expected_minimum = len(data["records"]) + len(data["sleep"])
    expected_maximum = expected_minimum + len(data["workouts"])
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/users/{user_id}/sync/runs", params={"limit": 200})
        response.raise_for_status()
        run = next((run for run in response.json() if run["run_id"] == "sdk_" + session_id), None)
        if run and run["status"] in {"failed", "partial", "cancelled", "unfinished", "stale"}:
            raise RuntimeError(f"Asynchronous batch failed ({run['status']}); checkpoint remains unconfirmed")
        if run and run["status"] == "success":
            if "dropped" in (run.get("message") or ""):
                raise RuntimeError("Worker dropped records; checkpoint remains unconfirmed")
            processed = run.get("items_processed")
            if processed is None or not expected_minimum <= processed <= expected_maximum:
                raise RuntimeError("Worker counts do not match the submitted batch")
            if run.get("provider") != "gadgetbridge" or run.get("user_id") != user_id:
                raise RuntimeError("Worker confirmation does not match the target")
            return run
        time.sleep(0.5)
    raise TimeoutError("No confirmed worker result before timeout; resume using the same checkpoint")


def finish_types(client: httpx.Client, user_id: str, session_id: str, data: dict[str, Any]) -> None:
    counts = Counter(record["type"] for record in data["records"])
    for collection in ["sleep", "workouts"]:
        if data[collection]:
            counts[collection] = len(data[collection])
    response = client.post(
        f"/api/v1/sdk/users/{user_id}/logs",
        json={
            "sdkVersion": SDK_VERSION,
            "provider": "gadgetbridge",
            "syncSessionId": session_id,
            "events": [
                {
                    "eventType": "historical_data_type_sync_end",
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "dataType": metric,
                    "success": True,
                    "recordCount": count,
                }
                for metric, count in counts.items()
            ],
        },
    )
    response.raise_for_status()


def upload_batches(
    client: httpx.Client,
    user_id: str,
    payloads: list[dict[str, Any]],
    checkpoint: Path,
    timeout: float = 120,
    retry_unconfirmed: bool = False,
) -> int:
    identity = {"url": str(client.base_url), "user_id": user_id, "export": fingerprint(payloads)}
    state: dict[str, Any] = (
        json.loads(checkpoint.read_text()) if checkpoint.exists() else {"target": identity, "batches": {}}
    )
    if state["target"] != identity:
        raise ValueError("Checkpoint belongs to another export, server or user")
    completed = 0
    for index, payload in enumerate(payloads):
        key = str(index)
        entry: dict[str, Any] | None = state["batches"].get(key)
        if entry and entry["verified"]:
            completed += 1
            continue
        send = entry is None or retry_unconfirmed
        if send:
            entry = {"session_id": str(uuid4()), "verified": False}
            state["batches"][key] = entry
            # Persist the attempt before posting; a lost response can be reconciled on resume.
            write_private_json(checkpoint, state)
            response = client.post(
                f"/api/v1/sdk/users/{user_id}/sync", json={**payload, "syncSessionId": entry["session_id"]}
            )
            response.raise_for_status()
            if response.status_code != 202:
                raise RuntimeError("Unexpected SDK acceptance response")
        assert entry is not None
        wait_for_batch(client, user_id, entry["session_id"], payload["data"], timeout)
        finish_types(client, user_id, entry["session_id"], payload["data"])
        entry["verified"] = True
        write_private_json(checkpoint, state)
        completed += 1
    return completed

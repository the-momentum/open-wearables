"""HTTP client of the Open Wearables Connect license server."""

from typing import Any
from uuid import UUID

import httpx

from app.config import settings
from app.utils.license_tokens import instance_token

TIMEOUT_SECONDS = 10


class LicenseServerError(Exception):
    """The license server answered with an error; code is its machine-readable error code."""

    def __init__(self, status_code: int, code: str | None, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class LicenseServerUnavailableError(Exception):
    """The license server could not be reached."""


class LicenseServerClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.license_server_url).rstrip("/")

    def register(self, private_key: str, instance_id: UUID, body: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/v1/instances", private_key, instance_id, json=body)

    def get_instance(self, private_key: str, instance_id: UUID) -> dict[str, Any]:
        return self._request("GET", f"/v1/instances/{instance_id}", private_key, instance_id)

    def delete_instance(self, private_key: str, instance_id: UUID) -> None:
        self._request("DELETE", f"/v1/instances/{instance_id}", private_key, instance_id)

    def get_entitlement(self, private_key: str, instance_id: UUID) -> dict[str, Any]:
        return self._request("GET", f"/v1/instances/{instance_id}/entitlement", private_key, instance_id)

    def release_seat(self, private_key: str, instance_id: UUID, pseudo_user_id: str) -> None:
        self._request(
            "POST",
            f"/v1/instances/{instance_id}/seats/release",
            private_key,
            instance_id,
            json={"pseudo_user_id": pseudo_user_id},
        )

    def _request(
        self,
        method: str,
        path: str,
        private_key: str,
        instance_id: UUID,
        json: dict[str, Any] | None = None,
    ) -> Any:
        headers = {"Authorization": f"Bearer {instance_token(private_key, instance_id)}"}
        try:
            response = httpx.request(
                method, f"{self.base_url}{path}", headers=headers, json=json, timeout=TIMEOUT_SECONDS
            )
        except httpx.HTTPError as exc:
            raise LicenseServerUnavailableError(str(exc)) from exc
        if response.status_code >= 500:
            raise LicenseServerUnavailableError(f"License server returned {response.status_code}")
        if response.status_code >= 400:
            code, message = _error_detail(response)
            raise LicenseServerError(response.status_code, code, message)
        return response.json() if response.content else None


def _error_detail(response: httpx.Response) -> tuple[str | None, str]:
    try:
        detail = response.json().get("detail")
    except ValueError:
        return None, response.text
    if isinstance(detail, dict):
        return detail.get("code"), str(detail.get("message", ""))
    return None, str(detail)


license_server_client = LicenseServerClient()

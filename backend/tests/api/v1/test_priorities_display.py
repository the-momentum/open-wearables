"""The provider priorities routes add each provider's display name and icon (the priority service cannot: the
provider strategies they come from import the services that rank sources through it)."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import ProviderPriority
from app.repositories import ProviderPriorityRepository
from app.schemas.enums import ProviderName


def test_priorities_carry_the_strategys_name_and_icon(
    client: TestClient, db: Session, api_v1_prefix: str, auth_headers: dict[str, str]
) -> None:
    ProviderPriorityRepository(ProviderPriority).upsert(db, ProviderName.GARMIN, 1)

    response = client.get(f"{api_v1_prefix}/priorities/providers", headers=auth_headers)

    assert response.status_code == 200
    first = response.json()["items"][0]
    assert (first["name"], first["icon_url"]) == ("Garmin", "/static/provider-icons/garmin.svg")


def test_a_provider_without_a_strategy_has_no_name_or_icon(
    client: TestClient, db: Session, api_v1_prefix: str, auth_headers: dict[str, str]
) -> None:
    """Rows for providers with no strategy (e.g. legacy 'unknown') still load, just without name and icon."""
    ProviderPriorityRepository(ProviderPriority).upsert(db, ProviderName.UNKNOWN, 1)

    response = client.get(f"{api_v1_prefix}/priorities/providers", headers=auth_headers)

    first = response.json()["items"][0]
    assert (first["provider"], first["name"], first["icon_url"]) == ("unknown", None, None)


def test_an_update_carries_them_too(client: TestClient, api_v1_prefix: str, auth_headers: dict[str, str]) -> None:
    response = client.put(f"{api_v1_prefix}/priorities/providers/garmin", headers=auth_headers, json={"priority": 1})

    assert (response.status_code, response.json()["name"]) == (200, "Garmin")


def test_api_key_reads_priorities(client: TestClient, api_v1_prefix: str, api_key_header: dict[str, str]) -> None:
    """Service callers (e.g. Ren's measurement pipeline) read priorities with the org API key, no JWT."""

    response = client.get(f"{api_v1_prefix}/priorities/providers", headers=api_key_header)

    assert response.status_code == 200
    assert all(item["provider"] for item in response.json()["items"])


def test_no_auth_is_still_rejected(client: TestClient, api_v1_prefix: str) -> None:
    response = client.get(f"{api_v1_prefix}/priorities/providers")

    assert response.status_code == 401


def test_api_key_cannot_update_priorities(
    client: TestClient, api_v1_prefix: str, api_key_header: dict[str, str]
) -> None:
    response = client.put(f"{api_v1_prefix}/priorities/providers/garmin", headers=api_key_header, json={"priority": 1})

    assert response.status_code == 401

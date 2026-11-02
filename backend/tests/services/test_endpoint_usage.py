"""Tests for the per-endpoint telemetry counters and their middleware."""

import contextlib
import re
from collections import Counter
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from app.config import settings
from app.main import api
from app.middlewares import _EndpointUsageMiddleware, add_endpoint_usage_middleware
from app.services.endpoint_usage import UNRESOLVED, _path_template, caller_type, endpoint_usage, usage_bucket
from app.services.sdk_token_service import create_sdk_user_token
from app.utils.security import create_access_token

USER_ID = "3f2b8c1e-0000-4000-8000-000000000001"


@pytest.fixture(autouse=True)
def _empty_buffer() -> Generator[None, None, None]:
    endpoint_usage._buffer = Counter()
    yield
    endpoint_usage._buffer = Counter()


def _build_client(*, telemetry_enabled: bool = True) -> TestClient:
    app = FastAPI()
    router = APIRouter()

    @router.get("/users/{user_id}")
    async def get_user(user_id: str) -> dict[str, str]:
        return {"id": user_id}

    @router.post("/providers/{provider}/webhooks")
    async def provider_webhook(provider: str) -> dict[str, str]:
        return {"provider": provider}

    @router.get("/users/{user_id}/events/menstrual-cycles")
    async def menstrual_cycles(user_id: str) -> list[str]:
        return []

    @router.get("/boom")
    async def boom() -> None:
        raise RuntimeError("kaboom")

    nested = APIRouter(prefix="/providers/{provider}/users/{user_id}")

    @nested.get("/workouts/{workout_id}")
    async def vendor_workout(provider: str, user_id: str, workout_id: str) -> dict[str, str]:
        return {"id": workout_id}

    router.include_router(nested)
    app.include_router(router, prefix=settings.api_v1)

    with patch.object(settings, "telemetry_enabled", telemetry_enabled):
        add_endpoint_usage_middleware(app)

    return TestClient(app, raise_server_exceptions=False)


def _recorded() -> dict[str, dict[str, dict[str, str]]]:
    endpoint_usage.flush()
    return endpoint_usage.read_day(datetime.now(timezone.utc).date())


class TestUsageBucket:
    @pytest.mark.parametrize(
        ("count", "expected"),
        [
            (1, "1-10"),
            (10, "1-10"),
            (11, "11-100"),
            (1_000, "101-1k"),
            (1_001, "1k-10k"),
            (1_000_000, "100k-1M"),
            (1_000_001, "1M+"),
        ],
    )
    def test_bucket_boundaries(self, count: int, expected: str) -> None:
        assert usage_bucket(count) == expected


class TestCallerType:
    def test_developer_jwt(self) -> None:
        assert caller_type(f"Bearer {create_access_token('dev-id')}", None) == "developer_jwt"

    def test_expired_developer_jwt_is_still_a_developer_call(self) -> None:
        token = create_access_token("dev-id", expires_delta=timedelta(minutes=-5))
        assert caller_type(f"Bearer {token}", None) == "developer_jwt"

    def test_sdk_token(self) -> None:
        assert caller_type(f"Bearer {create_sdk_user_token('app', USER_ID)}", None) == "sdk_token"

    def test_jwt_wins_over_api_key(self) -> None:
        assert caller_type(f"Bearer {create_access_token('dev-id')}", "sk-123") == "developer_jwt"

    def test_api_key(self) -> None:
        assert caller_type(None, "sk-123") == "api_key"

    def test_unusable_bearer_falls_back_to_api_key(self) -> None:
        assert caller_type("Bearer not-a-jwt", "sk-123") == "api_key"

    def test_token_signed_by_someone_else_is_not_ours(self) -> None:
        foreign = jwt.encode({"sub": "x"}, "another-secret", algorithm=settings.algorithm)
        assert caller_type(f"Bearer {foreign}", None) == "none"

    def test_no_credentials(self) -> None:
        assert caller_type(None, None) == "none"


class TestEndpointUsageMiddleware:
    def test_counts_by_route_template_never_by_raw_path(self) -> None:
        client = _build_client()
        client.get(f"{settings.api_v1}/users/{USER_ID}?token=secret", headers={"X-Open-Wearables-API-Key": "sk-1"})

        recorded = _recorded()

        assert recorded == {f"GET {settings.api_v1}/users/{{user_id}}": {"api_key": {"2xx": "1-10"}}}
        assert USER_ID not in str(recorded)
        assert "secret" not in str(recorded)

    def test_known_provider_is_kept_unknown_one_stays_a_placeholder(self) -> None:
        client = _build_client()
        client.post(f"{settings.api_v1}/providers/garmin/webhooks")
        client.post(f"{settings.api_v1}/providers/acme-health/webhooks")

        assert set(_recorded()) == {
            f"POST {settings.api_v1}/providers/garmin/webhooks",
            f"POST {settings.api_v1}/providers/{{provider}}/webhooks",
        }

    def test_nested_router_prefixes_are_part_of_the_template(self) -> None:
        client = _build_client()
        client.get(f"{settings.api_v1}/providers/oura/users/{USER_ID}/workouts/w-42")

        assert set(_recorded()) == {f"GET {settings.api_v1}/providers/oura/users/{{user_id}}/workouts/{{workout_id}}"}

    def test_docs_are_not_counted(self) -> None:
        client = _build_client()
        assert client.get("/docs").status_code == 200

        assert _recorded() == {}

    def test_unmatched_path_goes_to_a_single_bucket(self) -> None:
        client = _build_client()
        client.get(f"/wp-admin/{USER_ID}")

        assert _recorded() == {"unmatched": {"none": {"4xx": "1-10"}}}

    def test_sensitive_routes_are_not_counted(self) -> None:
        client = _build_client()
        client.get(f"{settings.api_v1}/users/{USER_ID}/events/menstrual-cycles")

        assert _recorded() == {}

    def test_preflight_is_not_counted(self) -> None:
        client = _build_client()
        client.options(f"{settings.api_v1}/users/{USER_ID}")

        assert _recorded() == {}

    def test_unhandled_exception_counts_as_5xx(self) -> None:
        client = _build_client()
        client.get(f"{settings.api_v1}/boom")

        assert _recorded() == {f"GET {settings.api_v1}/boom": {"none": {"5xx": "1-10"}}}

    def test_counts_are_bucketed(self) -> None:
        client = _build_client()
        for _ in range(11):
            client.get(f"{settings.api_v1}/users/{USER_ID}")

        assert _recorded() == {f"GET {settings.api_v1}/users/{{user_id}}": {"none": {"2xx": "11-100"}}}

    def test_opt_out_counts_nothing(self) -> None:
        client = _build_client(telemetry_enabled=False)
        client.get(f"{settings.api_v1}/users/{USER_ID}")

        assert endpoint_usage._buffer == Counter()
        assert _recorded() == {}

    def test_redis_failure_never_breaks_a_request(self) -> None:
        client = _build_client()
        with (
            patch.object(settings, "telemetry_usage_flush_interval_seconds", 0.0),
            patch("app.services.endpoint_usage.get_redis_client", side_effect=ConnectionError("down")),
        ):
            response = client.get(f"{settings.api_v1}/users/{USER_ID}")

        assert response.status_code == 200


class TestPathTemplate:
    def test_parameter_that_is_not_a_whole_segment_fails_closed(self) -> None:
        assert _path_template("/files/report-42.json", {"file_id": "42"}) == UNRESOLVED

    def test_value_is_never_emitted(self) -> None:
        assert _path_template(f"/users/{USER_ID}", {"user_id": USER_ID}) == "/users/{user_id}"


class TestRealRouteTable:
    """Pins the derived keys to the app's real routes, nested routers included."""

    @pytest.mark.skipif(
        not any(middleware.cls is _EndpointUsageMiddleware for middleware in api.user_middleware),
        reason="usage telemetry disabled in this environment",
    )
    def test_every_api_route_is_counted_under_its_full_template(self, client: TestClient) -> None:
        expected: set[str] = set()
        for template, operations in api.openapi()["paths"].items():
            if "/menstrual-cycles" in template:
                continue
            path = template.replace("{provider}", "not-a-provider")
            for name in set(re.findall(r"{(\w+)}", path)):
                path = path.replace(f"{{{name}}}", f"{name}-{USER_ID}")
            for method in operations.keys() & {"get", "post", "put", "patch", "delete"}:
                with contextlib.suppress(Exception):
                    client.request(method.upper(), path)
                expected.add(f"{method.upper()} {template}")

        recorded = _recorded()

        assert expected <= set(recorded)
        assert USER_ID not in str(recorded)

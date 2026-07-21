"""
Locust load tests for the Open Wearables API.

Usage (interactive UI):
    uv run --group load-test locust -f load_tests/locustfile.py --host http://localhost:8000

Usage (headless / CI):
    uv run --group load-test locust \
        -f load_tests/locustfile.py \
        --host $TARGET_HOST \
        --headless \
        --users 50 \
        --spawn-rate 5 \
        --run-time 60s \
        --csv /tmp/locust_results

Required environment variables (headless):
    LOAD_TEST_EMAIL     developer account email
    LOAD_TEST_PASSWORD  developer account password
    LOAD_TEST_API_KEY   API key (sk-... format)

Optional:
    LOAD_TEST_USER_ID   existing user UUID to target for per-user endpoints
"""

import json
import urllib.parse
import urllib.request
import uuid

from locust import HttpUser, between, events, task
from locust.exception import StopUser

from load_tests.settings import settings

# ---------------------------------------------------------------------------
# Shared state populated during the on_test_start hook
# ---------------------------------------------------------------------------
_shared: dict = {}


@events.test_start.add_listener
def on_test_start(environment, **_kwargs) -> None:  # noqa: ANN001
    """Authenticate once before the swarm starts and cache the token."""
    host = environment.host or "http://localhost:8000"

    if not settings.email or not settings.password:
        print("[locust] WARNING: LOAD_TEST_EMAIL / LOAD_TEST_PASSWORD not set. Developer-auth tasks will be skipped.")
        return

    data = urllib.parse.urlencode({"username": settings.email, "password": settings.password}).encode()
    req = urllib.request.Request(
        f"{host}/api/v1/auth/login",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read())
            _shared["access_token"] = body.get("access_token", "")
    except Exception as exc:
        print(f"[locust] WARNING: login failed ({exc}). Developer-auth tasks will use empty token.")
        _shared["access_token"] = ""


# ---------------------------------------------------------------------------
# Scenario 1 – Public / health endpoint
# ---------------------------------------------------------------------------
class HealthCheckUser(HttpUser):
    """Lightweight scenario that only hits the health endpoint."""

    weight = 1
    wait_time = between(1, 3)

    @task
    def health(self) -> None:
        self.client.get("/", name="GET /")


# ---------------------------------------------------------------------------
# Scenario 2 – API-key authenticated calls (external integrators)
# ---------------------------------------------------------------------------
class ApiKeyUser(HttpUser):
    """Simulates a third-party integrator using an API key."""

    weight = 3
    wait_time = between(0.5, 2)

    def on_start(self) -> None:
        if not settings.api_key:
            raise StopUser()
        self.headers = {"X-Open-Wearables-API-Key": settings.api_key}

    @task(3)
    def list_users(self) -> None:
        self.client.get("/api/v1/users?limit=20", headers=self.headers, name="GET /api/v1/users")

    @task(2)
    def get_user(self) -> None:
        if not settings.user_id:
            return
        self.client.get(
            f"/api/v1/users/{settings.user_id}",
            headers=self.headers,
            name="GET /api/v1/users/{user_id}",
        )

    @task(2)
    def list_sleep_events(self) -> None:
        if not settings.user_id:
            return
        self.client.get(
            f"/api/v1/users/{settings.user_id}/events/sleep"
            "?start_date=2024-01-01T00:00:00Z&end_date=2024-12-31T23:59:59Z&limit=20",
            headers=self.headers,
            name="GET /api/v1/users/{user_id}/events/sleep",
        )

    @task(2)
    def list_workout_events(self) -> None:
        if not settings.user_id:
            return
        self.client.get(
            f"/api/v1/users/{settings.user_id}/events/workouts"
            "?start_date=2024-01-01T00:00:00Z&end_date=2024-12-31T23:59:59Z&limit=20",
            headers=self.headers,
            name="GET /api/v1/users/{user_id}/events/workouts",
        )

    @task(1)
    def list_activity_summaries(self) -> None:
        if not settings.user_id:
            return
        self.client.get(
            f"/api/v1/users/{settings.user_id}/summaries/activity"
            "?start_date=2024-01-01T00:00:00Z&end_date=2024-12-31T23:59:59Z&limit=20",
            headers=self.headers,
            name="GET /api/v1/users/{user_id}/summaries/activity",
        )

    @task(1)
    def list_sleep_summaries(self) -> None:
        if not settings.user_id:
            return
        self.client.get(
            f"/api/v1/users/{settings.user_id}/summaries/sleep"
            "?start_date=2024-01-01T00:00:00Z&end_date=2024-12-31T23:59:59Z&limit=20",
            headers=self.headers,
            name="GET /api/v1/users/{user_id}/summaries/sleep",
        )


# ---------------------------------------------------------------------------
# Scenario 3 – Developer dashboard (JWT bearer token)
# ---------------------------------------------------------------------------
class DeveloperDashboardUser(HttpUser):
    """Simulates a developer using the management dashboard."""

    weight = 1
    wait_time = between(1, 4)

    def on_start(self) -> None:
        token = _shared.get("access_token", "")
        if not token:
            raise StopUser()
        self.headers = {"Authorization": f"Bearer {token}"}

    @task(3)
    def get_me(self) -> None:
        self.client.get("/api/v1/auth/me", headers=self.headers, name="GET /api/v1/auth/me")

    @task(2)
    def list_users(self) -> None:
        if not settings.api_key:
            return
        self.client.get(
            "/api/v1/users?limit=20",
            headers={"X-Open-Wearables-API-Key": settings.api_key},
            name="GET /api/v1/users (dev)",
        )

    @task(1)
    def list_api_keys(self) -> None:
        self.client.get(
            "/api/v1/developer/api-keys",
            headers=self.headers,
            name="GET /api/v1/developer/api-keys",
        )

    @task(1)
    def create_and_delete_user(self) -> None:
        """Creates a throwaway user then immediately deletes it."""
        if not settings.api_key:
            return
        key_headers = {"X-Open-Wearables-API-Key": settings.api_key}
        email = f"loadtest-{uuid.uuid4().hex[:8]}@example.com"
        with self.client.post(
            "/api/v1/users",
            json={"email": email},
            headers=key_headers,
            name="POST /api/v1/users",
            catch_response=True,
        ) as resp:
            if resp.status_code == 201:
                user_id = resp.json().get("id")
                if user_id:
                    self.client.delete(
                        f"/api/v1/users/{user_id}",
                        headers=key_headers,
                        name="DELETE /api/v1/users/{user_id}",
                    )
            else:
                resp.failure(f"Create user failed: {resp.status_code}")

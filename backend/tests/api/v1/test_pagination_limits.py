"""Guard: every endpoint over normalized data shares one page-size cap."""

from app.main import api
from app.utils.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

NORMALIZED_DATA_PATHS = [
    "/api/v1/users/{user_id}/timeseries",
    "/api/v1/users/{user_id}/events/workouts",
    "/api/v1/users/{user_id}/events/sleep",
    "/api/v1/users/{user_id}/events/menstrual-cycles",
    "/api/v1/users/{user_id}/summaries/activity",
    "/api/v1/users/{user_id}/summaries/sleep",
    "/api/v1/users/{user_id}/summaries/recovery",
    "/api/v1/users/{user_id}/health-scores",
]


class TestPaginationLimits:
    def test_normalized_data_endpoints_share_one_cap(self) -> None:
        schema = api.openapi()

        found = {}
        for path in NORMALIZED_DATA_PATHS:
            parameters = schema["paths"][path]["get"]["parameters"]
            limit = next(p for p in parameters if p["name"] == "limit")
            found[path] = (limit["schema"]["maximum"], limit["schema"]["default"])

        assert found == {path: (MAX_PAGE_SIZE, DEFAULT_PAGE_SIZE) for path in NORMALIZED_DATA_PATHS}

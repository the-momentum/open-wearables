"""Regression test for #2069: SDK auth must not hold the request-scoped session."""

import inspect
from collections.abc import Callable

from fastapi.dependencies.models import Dependant
from fastapi.dependencies.utils import get_dependant

from app.api.routes.v1.sdk_logs import submit_sdk_logs
from app.api.routes.v1.sdk_sync import get_sdk_sync_status
from app.database import _get_db_dependency
from app.utils.auth import get_sdk_auth


def _dependency_calls(endpoint: Callable) -> list:
    """Every dependency an endpoint resolves, nested ones included, built as FastAPI builds it."""
    calls: list = []

    def walk(dependant: Dependant) -> None:
        for sub in dependant.dependencies:
            calls.append(sub.call)
            walk(sub)

    walk(get_dependant(path="/", call=endpoint))
    return calls


class TestSdkAuthHoldsNoDbSession:
    def test_sdk_logs_auth_declares_no_request_session(self) -> None:
        """DbSession is a yield dependency, released only once the response completes."""
        deps = _dependency_calls(submit_sdk_logs)
        assert get_sdk_auth in deps
        assert _get_db_dependency not in deps
        assert _get_db_dependency in _dependency_calls(get_sdk_sync_status)

    def test_sdk_auth_runs_in_the_threadpool(self) -> None:
        assert not inspect.iscoroutinefunction(get_sdk_auth)

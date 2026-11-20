"""respx router used by the autouse ``respx_mock`` fixture."""

from typing import Any

import httpx
import respx
from respx.models import AllMockedAssertionError


class RecordingRouter(respx.MockRouter):
    """Remembers requests no route matched, so a test fails even when the code swallowed the error.

    Relies on respx resolving every request through ``resolve``/``aresolve``.
    """

    def __init__(self) -> None:
        super().__init__(assert_all_called=False, assert_all_mocked=True)
        self.unmatched: list[httpx.Request] = []

    def resolve(self, request: httpx.Request) -> Any:
        try:
            return super().resolve(request)
        except AllMockedAssertionError:
            self._record_unmatched(request)
            raise

    async def aresolve(self, request: httpx.Request) -> Any:
        try:
            return await super().aresolve(request)
        except AllMockedAssertionError:
            self._record_unmatched(request)
            raise

    def _record_unmatched(self, request: httpx.Request) -> None:
        """Leave the request to a router started inside the test, which respx tries after this one."""
        if self.Mocker is None or self.Mocker.routers[-1] is self:
            self.unmatched.append(request)

from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import HTTPException, Request, Response, status
from fastapi.routing import APIRoute
from starlette.types import Message, Receive


def _too_large(size: int, detail: Callable[[int], str]) -> HTTPException:
    # FastAPI turns any other exception raised while it parses the body into a 400.
    return HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=detail(size))


def limited_receive(request: Request, max_body: int, detail: Callable[[int], str]) -> Receive:
    """The request's receive channel, answering 413 with ``detail(body size)`` once the body outgrows ``max_body``."""
    # Clients that declare the size are rejected before any of the body is read.
    content_length = request.headers.get("content-length", "")
    if content_length.isdigit() and int(content_length) > max_body:
        raise _too_large(int(content_length), detail)

    receive = request.receive
    received = 0

    async def receive_within_limit() -> Message:
        nonlocal received
        message = await receive()
        if message["type"] == "http.request":
            received += len(message.get("body", b""))
            if received > max_body:
                raise _too_large(received, detail)
        return message

    return receive_within_limit


def body_limit_route(max_body: Callable[[], int], detail: Callable[[int], str]) -> type[APIRoute]:
    """A route class that answers 413 while an oversized body streams in, before FastAPI spools a form to disk.

    The connection stays open and the rest of the body is read and discarded, so clients that send the
    whole body before reading the response see the 413 rather than a reset.
    """

    class BodyLimitRoute(APIRoute):
        def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
            handler = super().get_route_handler()

            async def handler_within_limit(request: Request) -> Response:
                return await handler(Request(request.scope, limited_receive(request, max_body(), detail)))

            return handler_within_limit

    return BodyLimitRoute

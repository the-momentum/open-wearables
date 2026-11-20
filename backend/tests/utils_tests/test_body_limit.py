import pytest
from fastapi import HTTPException, Request

from app.utils.body_limit import limited_receive


def _detail(size: int) -> str:
    return f"{size}"


def _request(chunks: list[bytes], headers: list[tuple[bytes, bytes]] | None = None) -> tuple[Request, list[int]]:
    consumed = [0]

    async def receive() -> dict:
        consumed[0] += 1
        return {"type": "http.request", "body": chunks[consumed[0] - 1], "more_body": consumed[0] < len(chunks)}

    return Request({"type": "http", "headers": headers or []}, receive), consumed


async def test_raises_on_the_chunk_that_crosses_the_limit() -> None:
    request, consumed = _request([b"x" * 60, b"x" * 60, b"x" * 60])
    receive = limited_receive(request, 110, _detail)

    await receive()
    with pytest.raises(HTTPException) as exc_info:
        await receive()

    assert (exc_info.value.status_code, exc_info.value.detail) == (413, "120")
    assert consumed[0] == 2


async def test_passes_a_body_within_the_limit() -> None:
    request, _ = _request([b"x" * 60, b"x" * 50])
    receive = limited_receive(request, 110, _detail)

    first = await receive()
    second = await receive()

    assert (len(first["body"]), len(second["body"])) == (60, 50)
    assert second["more_body"] is False


def test_rejects_declared_length_before_reading() -> None:
    request, consumed = _request([b"x"], headers=[(b"content-length", b"111")])

    with pytest.raises(HTTPException) as exc_info:
        limited_receive(request, 110, _detail)

    assert (exc_info.value.status_code, exc_info.value.detail) == (413, "111")
    assert consumed[0] == 0

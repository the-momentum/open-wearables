from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

_sdk_manifest: ContextVar[dict[str, Any] | None] = ContextVar("sdk_manifest", default=None)


@contextmanager
def sdk_ingestion_context(manifest: dict[str, Any] | None) -> Iterator[None]:
    """Expose non-sensitive SDK transport metadata during one import commit."""

    token = _sdk_manifest.set(manifest)
    try:
        yield
    finally:
        _sdk_manifest.reset(token)


def current_sdk_ingestion_manifest() -> dict[str, Any] | None:
    manifest = _sdk_manifest.get()
    return dict(manifest) if manifest is not None else None


__all__ = ["current_sdk_ingestion_manifest", "sdk_ingestion_context"]

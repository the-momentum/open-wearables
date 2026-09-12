"""Tests for the OW_PATCHES_REQUIRED startup guard in app/__init__.py.

Regression cover for the 2026-08-20 incident: the homelab k8s image shipped
without `ow-patches/` (it lives at the repo root, outside the ./backend build
context), so `_apply_ow_patches()` silently returned and all 14 fork patches
were inert for weeks with no log line and a healthy-looking boot.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import app as app_pkg


@pytest.fixture
def patches_invisible(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate an image built without ow-patches.

    Two things have to be neutralised: the pre-loaded module short-circuit (the
    real patches are already applied by the time tests run) and Path.exists,
    which would otherwise find the checkout's real ow-patches directory.
    """
    monkeypatch.delitem(sys.modules, "_ow_patches_apply", raising=False)
    monkeypatch.setattr(Path, "exists", lambda self: False)


class TestOwPatchesRequiredGuard:
    @pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", " 1 "])
    def test_raises_when_required_and_missing(
        self, patches_invisible: None, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        monkeypatch.setenv("OW_PATCHES_REQUIRED", value)
        with pytest.raises(RuntimeError, match="OW_PATCHES_REQUIRED"):
            app_pkg._apply_ow_patches()

    def test_error_names_the_searched_paths(self, patches_invisible: None, monkeypatch: pytest.MonkeyPatch) -> None:
        """A bare 'not found' is what made this hard to diagnose."""
        monkeypatch.setenv("OW_PATCHES_REQUIRED", "1")
        monkeypatch.setenv("OW_PATCHES_DIR", "/some/explicit/override")
        with pytest.raises(RuntimeError) as exc_info:
            app_pkg._apply_ow_patches()
        message = str(exc_info.value)
        assert "/some/explicit/override" in message
        assert "Dockerfile.ow-patches" in message

    @pytest.mark.parametrize("value", ["", "0", "false", "no"])
    def test_silent_skip_when_not_required(
        self, patches_invisible: None, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        """Pure upstream checkouts must still boot unpatched."""
        monkeypatch.setenv("OW_PATCHES_REQUIRED", value)
        app_pkg._apply_ow_patches()  # must not raise

    def test_skip_when_env_absent(self, patches_invisible: None, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OW_PATCHES_REQUIRED", raising=False)
        app_pkg._apply_ow_patches()  # must not raise

    def test_skip_warns_on_stderr(
        self, patches_invisible: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Silent was the whole problem — an unpatched run must say so."""
        monkeypatch.delenv("OW_PATCHES_REQUIRED", raising=False)
        app_pkg._apply_ow_patches()
        assert "ow-patches" in capsys.readouterr().err


class TestOwPatchesPresentInCheckout:
    def test_real_checkout_resolves_and_applies(self) -> None:
        """Sanity: with nothing stubbed, the repo's own ow-patches is found."""
        apply_module = sys.modules.get("_ow_patches_apply")
        assert apply_module is not None, "ow-patches should have loaded at import time"
        enabled = apply_module.apply_patches()
        assert enabled.get("fix-provider-prefix-shadowing") is True

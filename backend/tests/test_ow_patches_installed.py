"""Assert every symbol the fork patches claim to replace is ACTUALLY replaced.

Why this exists
---------------
`tests/test_ow_patches_guard.py` only proves the ow-patches directory was found
and `apply_patches()` ran. It cannot tell you whether an individual patch
actually took effect. Two distinct silent failures have already happened:

1. The whole directory was missing from the deployed image, so nothing was
   patched at all (fixed by Dockerfile.ow-patches + OW_PATCHES_REQUIRED).
2. `fix-sleep-stages-missing` has two halves — a decorator over
   SummariesService.get_sleep_summaries, and a wholesale replacement of
   Ultrahuman247Data.normalize_sleep. The composer in apply.py loaded the module
   but never called `install()`, so the Ultrahuman half was inert while
   PATCHES.md asserted it was live. Nothing failed; Ultrahuman sleep stages just
   kept being parsed by upstream's strict, capitalisation-sensitive lookup.

A patched function's `__module__` is the dynamically-loaded patch module
(`_ow_patches_*`), whereas an unpatched one reports its upstream module. That
makes installation trivially checkable, so check it.
"""

from __future__ import annotations

import importlib

import pytest

import app  # noqa: F401  (importing app applies the patches)

# (import path, attribute chain, human label)
_EXPECTED_PATCHED: list[tuple[str, str, str]] = [
    # --- ultrahuman ---
    (
        # Retargeted 2026-08-29: upstream #1469 (152137fc) deleted
        # save_activity_samples and replaced it with the pure builder
        # _build_activity_samples, whose rows the caller bulk-upserts. Note this
        # case passed green while the patch was broken — monkey-patching CREATES
        # the attribute, so asserting __module__ cannot notice that upstream
        # deleted the method. The Ultrahuman provider tests are the real gate.
        "app.services.providers.ultrahuman.data_247",
        "Ultrahuman247Data._build_activity_samples",
        "fix-hrv-source-unknown",
    ),
    (
        "app.services.providers.ultrahuman.data_247",
        "Ultrahuman247Data.normalize_sleep",
        "fix-sleep-stages-missing (Ultrahuman half)",
    ),
    (
        "app.services.providers.ultrahuman.data_247",
        "Ultrahuman247Data.normalize_activity_samples",
        "fix-spo2-respiratory-missing",
    ),
    # --- garmin_connect (fork-only provider) ---
    # NOTE: save_daily_stats_for_date is deliberately NOT in this list. It used
    # to be replaced by fix-calories-total-mislabelled, but that override was
    # removed — garmin_connect is fork-only source we own, so the fix lives in
    # data_247.py directly. The patch shadowed later edits to the same file,
    # silently dropping newly-added fields. Asserting it is patched would now
    # be asserting the bug.
    # NOTE: load_and_save_all / _login / _get_api / _call_with_reauth are likewise
    # NOT listed. fix-garmin-connect-rate-limit-backoff replaced them until
    # 2026-09-13, when it was retired into client.py / data_247.py for the same
    # reason: it shadowed the fork's own later edit (the VO2max sync added to
    # load_and_save_all on 2026-08-29 never ran in production). Asserting these
    # are patched would enshrine that hazard.
    (
        "app.services.providers.garmin_connect.workouts",
        "GarminConnectWorkouts.load_data",
        "fix-garmin-connect-activity-hr-samples",
    ),
    # --- repositories ---
    (
        "app.repositories.health_score_repository",
        "HealthScoreRepository.get_with_filters",
        "fix-health-score-source-priority",
    ),
    (
        "app.repositories.event_record_repository",
        "EventRecordRepository.get_sleep_summaries",
        "fix-sleep-summary-utc-bucketing",
    ),
    (
        "app.repositories.event_record_repository",
        "EventRecordRepository._get_sleep_sessions",
        "fix-sleep-summary-utc-bucketing",
    ),
    (
        "app.repositories.data_point_series_repository",
        "DataPointSeriesRepository.get_daily_activity_aggregates",
        "fix-activity-summary-utc-bucketing",
    ),
    (
        "app.repositories.data_point_series_repository",
        "DataPointSeriesRepository.get_daily_active_minutes",
        "fix-activity-summary-utc-bucketing",
    ),
    (
        "app.repositories.data_point_series_repository",
        "DataPointSeriesRepository.get_daily_intensity_minutes",
        "fix-activity-summary-utc-bucketing",
    ),
    # --- services ---
    (
        "app.services.event_record_service",
        "EventRecordService.get_workouts",
        "fix-pace-null",
    ),
]

# Composed decorators live on the singleton, wrapped by apply.py's composers.
_EXPECTED_COMPOSED: list[tuple[str, str]] = [
    ("get_sleep_summaries", "fix-sleep-stages-missing + fix-sleep-timezone"),
    ("get_activity_summaries", "fix-calories-total-mislabelled + fix-summary-timezone-echo"),
]


def _resolve(module_path: str, chain: str) -> object:
    obj: object = importlib.import_module(module_path)
    for part in chain.split("."):
        obj = getattr(obj, part)
    return obj


@pytest.mark.parametrize(
    ("module_path", "chain", "label"),
    _EXPECTED_PATCHED,
    ids=[f"{c[1]}" for c in _EXPECTED_PATCHED],
)
def test_symbol_is_patched(module_path: str, chain: str, label: str) -> None:
    func = _resolve(module_path, chain)
    actual = getattr(func, "__module__", "<none>")
    assert actual.startswith("_ow_patches"), (
        f"{module_path}::{chain} is NOT patched — __module__ is {actual!r}, expected an "
        f"'_ow_patches*' module. The patch that should own it is {label}.\n"
        "Loading a patch module via _patch() does NOT install it; install() must be "
        "called (see _compose_sleep_summaries / _compose_activity_summaries in "
        "ow-patches/apply.py). A patch listed as enabled in PATCHES.md but not "
        "installed is silently inert."
    )


@pytest.mark.parametrize(("method", "label"), _EXPECTED_COMPOSED, ids=[c[0] for c in _EXPECTED_COMPOSED])
def test_composed_summary_method_is_wrapped(method: str, label: str) -> None:
    from app.services.summaries_service import summaries_service

    func = getattr(type(summaries_service), method)
    actual = getattr(func, "__module__", "<none>")
    assert actual.startswith("_ow_patches"), (
        f"SummariesService.{method} is NOT wrapped — __module__ is {actual!r}. Expected the composer for {label}."
    )


class TestRegistryConsistency:
    """`PATCHES_ENABLED` is only a flag dict — it does not drive installation.

    `apply_patches()` iterates `_STANDALONE_PATCHES`; the composers handle
    `_COMPOSED_PATCHES`. Adding a flag without adding the id to one of those
    tuples produces a patch that reports as enabled everywhere (PATCHES.md,
    check_upstream.py, apply_patches()'s return value) while never being
    installed. That is how fix-garmin-connect-rate-limit-backoff shipped inert:
    its tests called install() directly, so they passed.
    """

    @staticmethod
    def _registry():  # noqa: ANN205
        import sys

        module = sys.modules.get("_ow_patches_apply")
        assert module is not None, "ow-patches/apply.py was not loaded"
        return module

    # A third category: the composer implements the behaviour inline rather than
    # calling into the patch file, so the id legitimately appears in neither
    # tuple. fix-summary-timezone-echo is a one-liner
    # (`summary.timezone = user_tz` in _compose_activity_summaries), gated on its
    # own flag; its patch file is documentation only. Keep this list SHORT and
    # justify every entry — it is a hole in the guard.
    _INLINE_IN_COMPOSER = {
        "fix-summary-timezone-echo",
    }

    def test_every_enabled_patch_is_installed_or_composed(self) -> None:
        m = self._registry()
        wired = set(m._STANDALONE_PATCHES) | set(m._COMPOSED_PATCHES) | self._INLINE_IN_COMPOSER
        enabled = {pid for pid, on in m.PATCHES_ENABLED.items() if on}
        orphans = enabled - wired
        assert not orphans, (
            f"These patches are enabled in PATCHES_ENABLED but appear in neither "
            f"_STANDALONE_PATCHES nor _COMPOSED_PATCHES, so apply_patches() never "
            f"installs them: {sorted(orphans)}. They are silently inert. If a "
            f"composer implements one inline, add it to _INLINE_IN_COMPOSER with a "
            f"note saying where."
        )

    def test_inline_allowlist_entries_are_really_referenced_by_a_composer(self) -> None:
        """Don't let the allowlist rot into a way to hide a genuinely inert patch."""
        from pathlib import Path

        m = self._registry()
        apply_src = Path(m.__file__).read_text()
        for patch_id in self._INLINE_IN_COMPOSER:
            assert patch_id in apply_src, (
                f"{patch_id} is allowlisted as 'implemented inline by a composer' but "
                f"is not mentioned in apply.py at all — it is simply inert."
            )

    def test_no_wired_patch_lacks_a_flag(self) -> None:
        m = self._registry()
        wired = set(m._STANDALONE_PATCHES) | set(m._COMPOSED_PATCHES)
        missing_flag = wired - set(m.PATCHES_ENABLED)
        assert not missing_flag, (
            f"Wired for install but absent from PATCHES_ENABLED (so .get() returns "
            f"False and they never run): {sorted(missing_flag)}"
        )

    def test_every_patch_file_has_a_flag(self) -> None:
        from pathlib import Path

        m = self._registry()
        patch_dir = Path(m.__file__).resolve().parent / "local"
        on_disk = {p.stem for p in patch_dir.glob("*.py")}
        undeclared = on_disk - set(m.PATCHES_ENABLED)
        assert not undeclared, (
            f"Patch files with no PATCHES_ENABLED entry: {sorted(undeclared)}. "
            "Add a flag (True or False) and document them in PATCHES.md."
        )

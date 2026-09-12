"""Apply local fork patches at import time.

Each patch under ow-patches/local/<id>.py exposes an install() function. This
module imports the ones whose flag is True in PATCHES_ENABLED and calls them.

Setting any value to False is sufficient to revert that patch to upstream
behavior — no source files need to be touched. This is the A/B comparison
mechanism. Composed patches (multiple patches that target the same function)
are described in compose() below; their toggles still work independently.

Wiring: backend/app/__init__.py imports apply_patches() and calls it once at
process startup. Tests, the FastAPI app, Celery workers, and migration env.py
all go through that __init__ so all paths get patched.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Toggle dict — the single switchboard. Setting any value to False is enough
# to revert that patch to upstream behavior.
# ---------------------------------------------------------------------------
PATCHES_ENABLED: dict[str, bool] = {
    "fix-hrv-source-unknown": True,
    # Retired: upstream commit 09b7b0a now populates avg_hrv_sdnn_ms /
    # avg_hrv_rmssd_ms / avg_respiratory_rate / avg_spo2_percent in
    # get_sleep_summaries itself. See PATCHES.md.
    "fix-hrv-nightly-aggregate": False,
    "fix-pace-null": True,
    "fix-calories-total-mislabelled": True,
    "fix-spo2-respiratory-missing": True,
    "fix-sleep-stages-missing": True,
    "fix-sleep-timezone": True,
    # Retired: upstream #1242 (76ffff4) adds SeriesType.active_time →
    # active_time_minutes, preferred over the step heuristic in
    # get_activity_summaries, and the repo now excludes is_daily_total rows from
    # the per-minute bucket so it no longer collapses to 1. See PATCHES.md.
    # NOTE: active_minutes is still computed by the composed
    # fix-calories-total-mislabelled base_impl until that patch is rebased to a
    # decorator at merge time — this flag flip is bookkeeping ahead of the merge.
    "fix-active-minutes-broken": False,
    "fix-activity-summary-utc-bucketing": True,
    "fix-garmin-connect-activity-hr-samples": True,
    "fix-summary-timezone-echo": True,
    "fix-sleep-summary-utc-bucketing": True,
    "fix-health-score-source-priority": True,
    # Retired 2026-09-13: moved into source (garmin_connect/client.py +
    # data_247.py). Both files are fork-only, so the patch shadowed the fork's own
    # later edits — it hid the VO2max sync added to load_and_save_all on
    # 2026-08-29 for two weeks. See PATCHES.md retirement_note.
    "fix-garmin-connect-rate-limit-backoff": False,
    "fix-provider-prefix-shadowing": True,
}


_THIS_DIR = Path(__file__).resolve().parent
_LOCAL_DIR = _THIS_DIR / "local"


def _load_patch_module(patch_id: str):
    """Load ow-patches/local/<patch_id>.py as a module (filenames contain '-')."""
    path = _LOCAL_DIR / f"{patch_id}.py"
    if not path.exists():
        raise FileNotFoundError(f"patch file missing for {patch_id!r}: {path}")
    module_name = f"_ow_patches_{patch_id.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec and spec.loader, f"could not load spec for {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# Cache loaded patch modules so callers (compose, install) reach the same
# objects (e.g. the SUPPRESS_TIMEZONE flag on fix-sleep-timezone).
_LOADED: dict[str, object] = {}


def _patch(patch_id: str):
    if patch_id not in _LOADED:
        _LOADED[patch_id] = _load_patch_module(patch_id)
    return _LOADED[patch_id]


# ---------------------------------------------------------------------------
# Composer — for patches that share a target function.
# ---------------------------------------------------------------------------
#
# Two functions are decorated/replaced by more than one logical fix:
#
#   SummariesService.get_sleep_summaries     <- fix-sleep-stages-missing (always-emit stages)
#                                               + fix-sleep-timezone (timezone fields)
#
#   SummariesService.get_activity_summaries  <- fix-calories-total-mislabelled
#                                               + fix-summary-timezone-echo
#
# Both target functions are now OWNED by upstream — all four remaining patches
# are pure DECORATORS: the composer wraps upstream's method and post-processes
# each summary in the response, inheriting upstream changes instead of shadowing
# them (get_sleep_summaries: commit 09b7b0a; get_activity_summaries: #1242's
# active_time_minutes). fix-hrv-nightly-aggregate and fix-active-minutes-broken
# are retired (their fixes are now upstream). See PATCHES.md.
# ---------------------------------------------------------------------------


def _compose_sleep_summaries() -> None:
    """Wrap upstream's get_sleep_summaries with whichever of
    {sleep-stages-missing, sleep-timezone} are enabled.

    Both are pure decorators over upstream's response — they add fields, they
    don't reimplement the method. This means they automatically inherit any
    upstream changes to get_sleep_summaries (e.g. the avg_hrv_rmssd_ms field
    added in 09b7b0a) instead of shadowing them.
    """
    enabled_stages = PATCHES_ENABLED.get("fix-sleep-stages-missing", False)
    enabled_tz = PATCHES_ENABLED.get("fix-sleep-timezone", False)

    if not (enabled_stages or enabled_tz):
        return  # all upstream — no override

    stages_module = _patch("fix-sleep-stages-missing") if enabled_stages else None
    tz_module = _patch("fix-sleep-timezone") if enabled_tz else None

    if enabled_stages:
        # fix-sleep-stages-missing has TWO halves: the ensure_stages_object
        # decorator applied below, and a wrapper around
        # Ultrahuman247Data.normalize_sleep (capitalisation / key-name tolerance;
        # a wholesale replacement until 2026-08-29, now delegates to upstream).
        # Loading the module via _patch() does not install the latter — install()
        # must be called explicitly, exactly as _compose_activity_summaries does
        # for fix-calories-total-mislabelled. Without this the Ultrahuman half was
        # silently inert while PATCHES.md claimed it was live.
        stages_module.install()

    # NOTE: we deliberately fetch through sys.modules. `app.services` re-exports
    # the `summaries_service` singleton with `from .summaries_service import …`,
    # which shadows the submodule attribute on `app.services`. Using sys.modules
    # gets us the actual module object.
    import app.services.summaries_service  # noqa: F401, PLC0415  (ensures the module is registered in sys.modules)

    _module = sys.modules["app.services.summaries_service"]
    upstream_impl = _module.SummariesService.get_sleep_summaries

    def composed(self, db_session, user_id, start_date, end_date, cursor, limit):
        response = upstream_impl(
            self, db_session, user_id, start_date, end_date, cursor, limit
        )
        user_tz = None
        if enabled_tz:
            user = self.user_repo.get(db_session, user_id)
            user_tz = getattr(user, "timezone", None) if user else None
        for summary in response.data:
            if enabled_stages:
                stages_module.ensure_stages_object(summary)
            if enabled_tz:
                tz_module.apply_timezone_fields(summary, user_tz)
        return response

    _module.SummariesService.get_sleep_summaries = composed


def _compose_activity_summaries() -> None:
    """Decorate upstream's get_activity_summaries with the enabled activity fixes.

    Post-2026-07 merge these are pure post-processors over upstream's response,
    NOT a wholesale replacement — so they inherit upstream changes (e.g. #1242's
    active_time_minutes) instead of shadowing them:

      fix-calories-total-mislabelled : rewrite each summary's calorie fields
          (null total unless active+basal both present; surface basal). The
          Garmin-side basal persistence is structural (DAILIES_SERIES +
          garmin_connect override installed via cal_module.install()).
      fix-summary-timezone-echo      : stamp user.timezone on each summary.

    fix-active-minutes-broken is RETIRED (upstream's active_time_minutes is
    authoritative) — no active-minutes post-processing happens here anymore.
    """
    enabled_cal = PATCHES_ENABLED.get("fix-calories-total-mislabelled", False)
    enabled_tz_echo = PATCHES_ENABLED.get("fix-summary-timezone-echo", False)

    if not (enabled_cal or enabled_tz_echo):
        return  # all upstream — no override

    cal_module = _patch("fix-calories-total-mislabelled")
    if enabled_cal:
        # Installs the garmin_connect daily-stats override (persists basal energy).
        cal_module.install()

    # See _compose_sleep_summaries for why we reach through sys.modules.
    import app.services.summaries_service  # noqa: F401, PLC0415

    _module = sys.modules["app.services.summaries_service"]
    upstream_impl = _module.SummariesService.get_activity_summaries

    def composed(
        self, db_session, user_id, start_date, end_date, cursor, limit, sort_order="asc"
    ):
        response = upstream_impl(
            self, db_session, user_id, start_date, end_date, cursor, limit, sort_order
        )
        user_tz = None
        if enabled_tz_echo:
            user = self.user_repo.get(db_session, user_id)
            user_tz = getattr(user, "timezone", None) if user else None
        for summary in response.data:
            if enabled_cal:
                cal_module.apply_calories_fix(summary)
            if enabled_tz_echo:
                summary.timezone = user_tz
        return response

    _module.SummariesService.get_activity_summaries = composed


# ---------------------------------------------------------------------------
# Patches that don't overlap with any other patch — straight install.
# ---------------------------------------------------------------------------
_STANDALONE_PATCHES = (
    "fix-hrv-source-unknown",
    "fix-pace-null",
    "fix-spo2-respiratory-missing",
    "fix-activity-summary-utc-bucketing",
    "fix-garmin-connect-activity-hr-samples",
    "fix-sleep-summary-utc-bucketing",
    "fix-health-score-source-priority",
    # fix-garmin-connect-rate-limit-backoff is retired into source — see PATCHES.md.
    "fix-provider-prefix-shadowing",
)

# Patches whose runtime behavior is composed (no direct install call) live in
# the composers above, but their files still need to be loadable so check_upstream
# and the composer can read flags off them.
# (fix-hrv-nightly-aggregate is retired — its file is kept for reference but is
# no longer loaded or composed.)
_COMPOSED_PATCHES = (
    "fix-calories-total-mislabelled",
    "fix-sleep-stages-missing",
    "fix-sleep-timezone",
    # fix-active-minutes-broken is retired (superseded by upstream #1242) — no
    # longer composed or loaded; its file is kept for reference. See PATCHES.md.
)


# ---------------------------------------------------------------------------
# Public entry point.
# ---------------------------------------------------------------------------

_APPLIED = False


def apply_patches() -> dict[str, bool]:
    """Apply all enabled patches. Idempotent — safe to call multiple times.

    Returns the PATCHES_ENABLED mapping (a copy) so callers can log/inspect.
    """
    global _APPLIED
    if _APPLIED:
        return dict(PATCHES_ENABLED)

    for patch_id in _STANDALONE_PATCHES:
        if not PATCHES_ENABLED.get(patch_id, False):
            logger.info("ow-patches: %s DISABLED", patch_id)
            continue
        try:
            module = _patch(patch_id)
            module.install()
            logger.info("ow-patches: %s applied", patch_id)
        except Exception as exc:
            logger.exception("ow-patches: %s FAILED to apply: %s", patch_id, exc)
            raise

    # Composers — each handles its own toggle logic internally.
    try:
        _compose_sleep_summaries()
    except Exception:
        logger.exception("ow-patches: failed to compose get_sleep_summaries")
        raise
    try:
        _compose_activity_summaries()
    except Exception:
        logger.exception("ow-patches: failed to compose get_activity_summaries")
        raise

    # Touch composed-only patch modules so they're loaded (helpful for
    # check_upstream introspection).
    for patch_id in _COMPOSED_PATCHES:
        try:
            _patch(patch_id)
        except FileNotFoundError:
            logger.warning(
                "ow-patches: composed patch %s has no file (skipping load)", patch_id
            )

    _APPLIED = True
    return dict(PATCHES_ENABLED)


if __name__ == "__main__":
    # Allow `python ow-patches/apply.py` for sanity-checking.
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # Ensure backend/ is importable when invoked directly.
    repo_root = _THIS_DIR.parent
    sys.path.insert(0, str(repo_root / "backend"))
    apply_patches()
    print("ow-patches applied:")
    for patch_id, enabled in PATCHES_ENABLED.items():
        print(f"  {patch_id:35s} {'ENABLED' if enabled else 'disabled'}")

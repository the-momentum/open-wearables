# Fork Patches Registry

Source of truth for every place this fork diverges from upstream.
See `../FORK.md` for how the patch system works and when to patch versus edit
directly, and the `upstream-reconcile` skill for the merge procedure. Run `python ow-patches/check_upstream.py`
to see whether upstream has caught up to any of these.

Upstream: https://github.com/the-momentum/open-wearables

This file has two halves:

1. **Backend Patches** — runtime monkey-patched via `apply.py`. Each is
   independently toggleable. `check_upstream.py` covers these.
2. **Frontend Patches (Source Edits)** — direct edits to `frontend/src/`,
   not toggleable at runtime (the app is built once and served as static
   assets). Documented for institutional memory.

**`replacement_kind` field.** Each patch declares how it relates to upstream so
`check_upstream.py` can escalate drift correctly:

- `wholesale-replace` (default if omitted) — the patch reimplements an upstream
  method/body. These SHADOW upstream: a `git merge` will not conflict (we never
  edit the upstream source file), so if upstream rewrites the method our copy
  silently wins and drops upstream's changes. Drift on these is a **shadow risk**.
- `decorate` — the patch wraps upstream's method and only post-processes the
  result. It inherits upstream changes; drift is lower-risk (re-verify only).
- `structural` — source edits (schema fields, columns, frontend). Upstream drift
  surfaces as ordinary git conflicts at merge time, so the runtime drift check
  doesn't apply.
- `standalone` — a self-contained helper/function swap with no upstream body to
  go stale.

When in doubt, leave it `wholesale-replace`: a false "re-verify" costs one manual
diff; a missed shadow is how `avg_hrv_rmssd_ms` silently went null.

---

## ⚠ Deployment requirement — the patches must be IN the image

`ow-patches/` lives at the **repo root**, but upstream's backend image is built
with `./backend` as the context. So `ow-patches` is not in that context and
cannot be `COPY`ed by `backend/Dockerfile` (Docker forbids `COPY ../`). If it
isn't put there some other way, `_apply_ow_patches()` in `backend/app/__init__.py`
finds nothing and returns — and **every patch in this file silently no-ops**.
The app boots clean. Nothing logs. The structural halves (DB columns, schema
fields, frontend edits) are still present, so you get the exact
"fields exist but are always null" symptom that a disabled patch produces.

**This happened.** On 2026-08-20 the homelab k8s cluster was found with
`/root_project/ow-patches` **absent** and all 14 patches inert — for weeks. The
deployments had no `volumeMounts` and no `OW_PATCHES_DIR`. The old
`docker-compose.prod.yml` bind-mounted the directory (its comment warned about
precisely this failure), but upstream deleted that file in #1429 and the k8s
manifests never replaced the mount.

Three guards now exist; keep all three:

1. **`Dockerfile.ow-patches`** (repo root) — fork-owned overlay that layers
   `ow-patches` onto the upstream-built backend image and sets
   `OW_PATCHES_DIR` + `OW_PATCHES_REQUIRED`. Both CI
   (`.github/workflows/publish-ghcr.yml`) and `scripts/build-push.sh` build
   through it, and both then assert `apply.py` is present in the result.
2. **`OW_PATCHES_REQUIRED=1`** — makes a missing directory a hard startup
   failure instead of a silent skip. Deployments of this fork should always set
   it. Unset, an unpatched run now at least warns on stderr. Covered by
   `backend/tests/test_ow_patches_guard.py`.
3. **Deployment manifests** must run the overlay image. If you build the
   backend with a plain `podman build ./backend`, you will ship an unpatched
   image again.

Quick check against a running cluster:

```bash
kubectl -n open-wearables exec deploy/app -- ls /root_project/ow-patches/apply.py
```

---

## fix-hrv-source-unknown

- patch_id:                  fix-hrv-source-unknown
- status:                    upstream_candidate
- upstream_url:              https://github.com/the-momentum/open-wearables
- upstream_issue_or_pr:      null
- file:                      backend/app/services/providers/ultrahuman/data_247.py
- symbol:                    Ultrahuman247Data._build_activity_samples
- what_we_changed:           Pass `source=self.provider_name` (not `provider=`) when constructing TimeSeriesSampleCreate so the data_source row carries a non-null source label and consumers don't get back `"unknown"`.
- rebased_note:              Rebased 2026-07-26 onto merged upstream. Upstream rewrote save_activity_samples: now resolves series via ACTIVITY_SAMPLE_SERIES.get (#1206) and passes is_daily_total=daily_total_flag(...) (#1232). Patch body is now upstream's current body with `source=self.provider_name` added alongside `provider=` (both kept) — the inline type_mapping and missing is_daily_total that were shadowing upstream are gone.
- retire_when:               Ultrahuman247Data._build_activity_samples passes `source=` (not just `provider=`) to TimeSeriesSampleCreate, OR the TimeSeriesSampleCreate constructor itself populates source from provider when source is omitted.
- upstream_equivalent_check: providers/ultrahuman/data_247.py::source=self.provider_name
- rebased_note_2:            2026-08-29: RETARGETED. Upstream #1469 (152137fc) deleted `save_activity_samples` outright and removed `self.data_point_repo` from Ultrahuman247Data / Base247DataTemplate, replacing per-row `repo.create()` writes with the pure builder `_build_activity_samples` whose rows the caller bulk-upserts via `timeseries_service.bulk_create_samples`. The stale copy still called `self.data_point_repo.create(...)`, which raised AttributeError inside the per-sample `except Exception` — so EVERY Ultrahuman timeseries sample (HR, HRV, temp, steps, SpO2, respiratory) was silently dropped while the sync still reported success. Patch is now upstream's current `_build_activity_samples` body with the single added `source=self.provider_name`. NOTE test_ow_patches_installed.py stayed GREEN throughout the breakage: monkey-patching creates the attribute, so asserting `__module__` cannot detect that upstream deleted the method. Upstream's own provider tests are the real gate.
- audit_note:                2026-09-13 vs 53de57ca — KEEP. providers/ultrahuman/ untouched upstream in the range.
- local_patch_file:          ow-patches/local/fix-hrv-source-unknown.py

---

## fix-hrv-nightly-aggregate

- patch_id:                  fix-hrv-nightly-aggregate
- status:                    retired
- retired_in:                upstream commit 09b7b0a ("Oura missed commit and sleep summary metrics"), merged 2026-06-07
- upstream_url:              https://github.com/the-momentum/open-wearables
- upstream_issue_or_pr:      null
- file:                      backend/app/services/summaries_service.py
- symbol:                    SummariesService.get_sleep_summaries
- what_we_changed:           Compute mean SDNN HRV, respiratory rate, and SpO2 over the sleep window padded by ±30min, populating avg_hrv_sdnn_ms / avg_respiratory_rate / avg_spo2_percent on each SleepSummary record (instead of always-null TODOs). Raw intraday samples remain untouched.
- retire_when:               get_sleep_summaries response includes avg_hrv_sdnn_ms as a non-null float when intraday SDNN samples exist within the sleep window.
- retirement_note:           Upstream rewrote get_sleep_summaries to populate avg_hrv_sdnn_ms / avg_respiratory_rate / avg_spo2_percent itself AND added a new avg_hrv_rmssd_ms field. Upstream averages over the EXACT sleep window (we padded ±30min) and does not round SDNN — both are accepted regressions on retirement. Our wholesale-replacement patch was shadowing upstream's new avg_hrv_rmssd_ms (leaving it null), which is why it was retired rather than kept. The marker SLEEP_PHYSIO_WINDOW_PAD never matched upstream (it is unique to our impl), so check_upstream.py could not auto-flag this — see the shadow-audit phase of the `upstream-reconcile` skill.
- upstream_equivalent_check: SLEEP_PHYSIO_WINDOW_PAD
- local_patch_file:          ow-patches/local/fix-hrv-nightly-aggregate.py

---

## fix-pace-null

- patch_id:                  fix-pace-null
- status:                    upstream_candidate
- upstream_url:              https://github.com/the-momentum/open-wearables
- upstream_issue_or_pr:      null
- file:                      backend/app/services/event_record_service.py
- symbol:                    EventRecordService.get_workouts
- what_we_changed:           Compute avg_pace_sec_per_km in the workout list response (was hard-coded None) using the same derivation as the detailed view: 1000/average_speed if present, else duration_seconds/(distance_meters/1000), restricted to WORKOUTS_WITH_PACE.
- retire_when:               Workout list response (get_workouts → Workout.avg_pace_sec_per_km) returns a non-null int for running/walking/cycling workouts that have distance and duration.
- upstream_equivalent_check: _compute_avg_pace_sec_per_km
- rebased_note:              2026-09-13: rebased onto upstream 53de57ca. Upstream #1510 (e5955636) added `name=details.label`, `entry_source=details.entry_source` and `intensity=details.intensity` to the `Workout(...)` constructor in get_workouts; the wholesale copy still passed `name=None` and lacked the other two, so the LIST endpoint returned all three as null while the DETAIL endpoint populated them — FORK.md failure mode #4, invisible to the suite (test_workouts.py only asserts id/type/start/end/duration). Re-applied all three. Verified `dad8b3be` touched only the sleep-webhook kwargs, not get_workouts. retire_when NOT met: upstream still hard-codes `avg_pace_sec_per_km=None` (event_record_service.py ~L828). NOTE test_ow_patches_column_drift.py does not cover service-level patches — this drift class has no guard; see the reconcile report.
- local_patch_file:          ow-patches/local/fix-pace-null.py

---

## fix-calories-total-mislabelled

- patch_id:                  fix-calories-total-mislabelled
- status:                    upstream_candidate
- replacement_kind:          decorate
- upstream_url:              https://github.com/the-momentum/open-wearables
- upstream_issue_or_pr:      null
- file:                      backend/app/services/providers/garmin/coverage.py, backend/app/services/providers/garmin_connect/data_247.py, backend/app/services/summaries_service.py
- symbol:                    DAILIES_SERIES (basal mapping, structural) + GarminConnect247Data.save_daily_stats_for_date + SummariesService.get_activity_summaries (decorated)
- what_we_changed:           Persist `bmrKilocalories` as SeriesType.basal_energy from both Garmin providers, surface it on ActivitySummary as basal_calories_kcal, and stop computing total_calories_kcal as `active + 0` when basal is missing — return null so the field name is honest (active+basal, not active-only).
- rebased_note:              Rebased 2026-07-26 onto merged upstream. Was a wholesale-replace of Garmin247Data._build_dailies_samples + get_activity_summaries, which shadowed #1232 (is_daily_total) and #1242 (active_time_minutes). Now: (1) Garmin OAuth basal is a one-line STRUCTURAL add to garmin/coverage.py::DAILIES_SERIES (upstream's own _build_dailies_samples persists it with the correct daily_total_flag — no shadow); (2) get_activity_summaries is a DECORATOR (apply_calories_fix in apply.py) that reconstructs basal = total - active from upstream's output and nulls total unless both present, inheriting #1242's active_time_minutes instead of shadowing it; (3) garmin_connect override retained (fork-only provider) and now stamps is_daily_total via daily_total_flag.
- retire_when:               Garmin daily-stats normalization persists basal energy AND ActivitySummary.total_calories_kcal is null when basal is missing (not equal to active_calories_kcal) AND ActivitySummary.basal_calories_kcal is populated.
- upstream_equivalent_check: basal_calories_kcal
- rebased_note_2:            2026-08-20: the `GarminConnect247Data.save_daily_stats_for_date` override was REMOVED from this patch. garmin_connect is a fork-only provider whose source we own outright, so persisting bmrKilocalories belongs in data_247.py directly — and keeping it as a runtime patch actively shadowed later edits to the very file it patched: new fields added to the real save_daily_stats_for_date (floorsAscended -> flights_climbed, intensity minutes -> exercise_time) silently never ran, with no error and no failing test. Patching your own source buys every shadowing hazard and none of the upstream-conflict benefit. This patch is now decorator-only (apply_calories_fix over get_activity_summaries) plus the structural garmin/coverage.py DAILIES_SERIES basal mapping; install() is a documented no-op.
- audit_note:                2026-09-13 vs 53de57ca — KEEP. check_upstream.py flagged e5955636, but that commit did not touch summaries_service.py (it only added entry_source/label to garmin/coverage.py WORKOUT_FIELDS); `git log f766b5a0..53de57ca -- summaries_service.py` is empty. Composer signature `(self, db_session, user_id, start_date, end_date, cursor, limit, sort_order="asc")` still matches upstream exactly; DAILIES_SERIES basal tuple intact and consumed the same way; upstream still computes total = active + (basal or 0) and never sets basal_calories_kcal, so retire_when is unmet.
- local_patch_file:          ow-patches/local/fix-calories-total-mislabelled.py

---

## fix-spo2-respiratory-missing

- patch_id:                  fix-spo2-respiratory-missing
- status:                    upstream_candidate
- upstream_url:              https://github.com/the-momentum/open-wearables
- upstream_issue_or_pr:      null
- file:                      backend/app/services/providers/ultrahuman/data_247.py, backend/app/services/providers/ultrahuman/coverage.py
- symbol:                    Ultrahuman247Data.normalize_activity_samples + Ultrahuman247Data.load_and_save_all + ACTIVITY_SAMPLE_SERIES (coverage, structural)
- what_we_changed:           Map Ultrahuman intraday SpO2 (spo2/oxygen_saturation/blood_oxygen) and respiratory rate (respiratory_rate/breath_rate/breathing_rate/breath) tokens to SeriesType.oxygen_saturation and SeriesType.respiratory_rate. Fall back to the Sleep object's `spo2.value` (single nightly average emitted at sleep midpoint) when intraday samples aren't returned.
- rebased_note:              Rebased 2026-07-26 onto merged upstream. Upstream rewrote load_and_save_all to add an active_minutes → SeriesType.active_time ingestion block (#1242); the stale copy predated it and dropped it. Now upstream's current normalize_activity_samples / load_and_save_all bodies with our SpO2/respiratory tokens + Sleep.spo2 fallback re-applied. Because upstream #1206 removed the inline type_mapping (now ACTIVITY_SAMPLE_SERIES.get), the two new SeriesTypes MUST be resolvable via that constant — added `spo2`/`respiratory_rate` to ultrahuman/coverage.py::ACTIVITY_SAMPLE_SERIES (STRUCTURAL; TIMESERIES derives from it, so the coverage tab advertises them).
- retire_when:               get_timeseries response for ultrahuman provider returns at least one record with type=oxygen_saturation or type=respiratory_rate when the user has data for those metrics.
- upstream_equivalent_check: providers/ultrahuman/data_247.py::_RESPIRATORY_TYPES
- rebased_note_3:            2026-08-29 (same day, follow-up): the rebase below introduced a REGRESSION. In copying upstream's `load_and_save_all` body faithfully, it dropped `source=self.provider_name` from the `vo2_max` and `active_time` TimeSeriesSampleCreate calls (upstream omits it; the pre-rebase fork copy had it). Because the DataSource identity is `(user_id, device_model, source)`, those two series immediately began writing to a NULL-source `data_source` row while every other Ultrahuman series wrote to the correct one — splitting the provider's history across two identities, with no error and no failing test. Found by inspecting production `data_source` rows, which is far too late. Both `source=` arguments restored, and the invariant is now enforced by backend/tests/test_ow_patches_identity_drift.py.
- rebased_note_2:            2026-08-29: rebased onto upstream #1469 (152137fc, "report real synced item counts"). The stale `load_and_save_all` copy predated the whole rewrite and shadowed it: it called the now-deleted `save_activity_samples`, wrote rows one at a time through the removed `self.data_point_repo` (AttributeError on the vo2_max path aborted the day and the `active_time` block was never reached), returned plain ints instead of `WriteCounts` — which the orchestrator reads via `.inserted`, silently yielding 0, reintroducing the exact "Success but 0 items" bug #1469 fixed — and bypassed both the `ON CONFLICT` upsert (so re-syncs duplicated rows) and the `on_timeseries_batch_saved` webhook. Now upstream's current body with ONLY the two fork deltas re-applied: the widened `intraday_types` list and the Sleep-object SpO2 midpoint fallback. `normalize_activity_samples` verified byte-identical to upstream apart from our two buckets; coverage.py's ACTIVITY_SAMPLE_SERIES additions survived the merge and sit alongside upstream's a09bd015 `temperature -> skin_temperature` change.
- audit_note:                2026-09-13 vs 53de57ca — KEEP. providers/ultrahuman/ untouched upstream in the range.
- local_patch_file:          ow-patches/local/fix-spo2-respiratory-missing.py

---

## fix-sleep-stages-missing

- patch_id:                  fix-sleep-stages-missing
- status:                    upstream_candidate
- upstream_url:              https://github.com/the-momentum/open-wearables
- upstream_issue_or_pr:      null
- file:                      backend/app/services/providers/ultrahuman/data_247.py, backend/app/services/summaries_service.py
- symbol:                    Ultrahuman247Data.normalize_sleep + SummariesService.get_sleep_summaries
- replacement_kind:          decorate
- what_we_changed:           Make Ultrahuman sleep-stage parsing robust to capitalization and key-name variants (deep / Deep Sleep / deep_sleep; stage_time / duration). Always emit the SleepStagesSummary object on SleepSummary responses (with null fields if the source doesn't track stages) so consumers can distinguish "source doesn't expose stages" from "feature not implemented". The summary-side change is now a decorator over upstream's get_sleep_summaries (ensure_stages_object), not a wholesale replacement — see apply.py.
- retire_when:               get_sleep_summary response.data[*].stages is always an object (never null/missing) when sleep records exist, AND ultrahuman sleep stages parse correctly when upstream returns them with the canonical type tokens.
- upstream_equivalent_check: stage_aliases
- rebased_note_3:            2026-08-29: CONVERTED normalize_sleep from a wholesale body replacement to a WRAPPER. Upstream #1476 (3a10de4f) added `"stage_timestamps": self._normalize_sleep_stages(raw_sleep)` to the dict this patch replaced; our copy had no such key, so `save_sleep_data` read `None` and the new `sleep_details.sleep_stages` JSONB column was never populated for Ultrahuman — upstream's entire granular-stages feature silently reverted, and two new upstream tests failed with KeyError. Rather than re-add the one key (which would shadow the next addition the same way), `normalize_sleep` now calls upstream's method and overwrites ONLY the four aggregate stage counts, so every key upstream adds later is inherited for free. install() captures the original once, guarded for idempotency. Same wholesale->decorate migration already applied to fix-calories-total-mislabelled and fix-sleep-timezone.
- rebased_note_2:            2026-08-20: the Ultrahuman half of this patch was SILENTLY INERT. `_compose_sleep_summaries` loaded the module via `_patch()` but never called `install()`, so Ultrahuman247Data.normalize_sleep was still upstream's strict, capitalisation-sensitive lookup while this file asserted the fix was live. Fixed by calling `stages_module.install()` in the composer (mirroring what `_compose_activity_summaries` already did for fix-calories-total-mislabelled). Guarded by backend/tests/test_ow_patches_installed.py, which asserts every patched symbol's `__module__` is an `_ow_patches*` module.
- audit_note:                2026-09-13 vs 53de57ca — KEEP. Upstream did not touch providers/ultrahuman/ or summaries_service.py in the range; sleep composer signature `(self, db_session, user_id, start_date, end_date, cursor, limit)` still matches; SleepStagesSummary fields unchanged.
- local_patch_file:          ow-patches/local/fix-sleep-stages-missing.py

---

## fix-sleep-timezone

- patch_id:                  fix-sleep-timezone
- status:                    local_only
- upstream_url:              https://github.com/the-momentum/open-wearables
- upstream_issue_or_pr:      null
- file:                      backend/app/models/user.py, backend/app/schemas/responses/activity/summaries.py, backend/app/services/summaries_service.py, backend/migrations/versions/2026_05_05_1200-9b3d4f7a8c21_user_timezone.py
- symbol:                    User.timezone (column) + SleepSummary (timezone/start_time_local/end_time_local fields) + SummariesService.get_sleep_summaries (population)
- replacement_kind:          decorate
- what_we_changed:           Added User.timezone (IANA, VARCHAR(50)) DB column + migration; added timezone, start_time_local, end_time_local fields to SleepSummary; populated them in get_sleep_summaries from the user's timezone. The DB column and migration are structural and not toggleable from apply.py — only the response population is. The population is now a decorator over upstream's get_sleep_summaries (apply_timezone_fields), not a wholesale replacement — see apply.py. With the patch disabled, the columns/fields exist but contain None.
- retire_when:               UserRead response includes a timezone field AND sleep summaries surface a per-record local datetime or a top-level user.timezone the consumer can apply.
- upstream_equivalent_check: start_time_local
- audit_note:                2026-09-13 vs 53de57ca — KEEP. Written fields (timezone, start_time_local, end_time_local) are fork-structural on SleepSummary and survived the merge; upstream still has no User.timezone.
- local_patch_file:          ow-patches/local/fix-sleep-timezone.py

---

## fix-activity-summary-utc-bucketing

- patch_id:                  fix-activity-summary-utc-bucketing
- status:                    local_only
- upstream_url:              https://github.com/the-momentum/open-wearables
- upstream_issue_or_pr:      null
- file:                      backend/app/repositories/data_point_series_repository.py
- symbol:                    DataPointSeriesRepository.get_daily_activity_aggregates + .get_daily_active_minutes + .get_daily_intensity_minutes
- what_we_changed:           Bucket the three daily activity aggregator queries by user-local date instead of UTC. Resolves the bug where workouts crossing a UTC midnight (e.g. a Sunday morning trail run in Brisbane that starts 21:14 UTC Saturday) split across two day-cards in the API and the user's "Sunday" card shows post-run HR (~81/128) instead of trail-run HR (~161/186). Zone-offset-first: honour a populated EventRecord.zone_offset, else `(recorded_at AT TIME ZONE user.timezone)::date`, else UTC.
- rebased_note:              Rebased 2026-07-26 onto merged upstream. Upstream rewrote all three aggregators: #1232 added prefer_daily_sum / is_daily_total de-duplication; #1242 added SeriesType.active_time → active_time_minutes and DataSource.provider in SELECT/GROUP BY/return dict. The stale wholesale copies used naive func.sum(case(...)) and shadowed both (reintroducing daily-total double-count and dropping active_time_minutes/provider). Now upstream's current three bodies with ONLY the date-bucket sub-expression swapped to the zone_offset-first / user.timezone / UTC coalesce.
- retire_when:               DataPointSeriesRepository.get_daily_activity_aggregates groups by user-local date (any of: AT TIME ZONE user.timezone, ZoneInfo-based bucketing, per-row zone_offset cast). Marker: any reference to `_local_date_bucket_expr` or equivalent timezone-aware bucketing helper in DataPointSeriesRepository.
- upstream_equivalent_check: backend/app/repositories/data_point_series_repository.py::_local_date_bucket_expr
- rebased_note_3:            2026-09-13: audited against upstream 53de57ca — KEEP AS-IS. check_upstream.py flagged c8409b55 / 7bc9c27e / 6c672e74 as shadow risk; all three touched other parts of the file (user timeline counts, WriteCounts, the COPY+staging bulk upsert). ast-extracted bodies of the three replaced methods are identical between f766b5a0 and 53de57ca, and the patch differs from them only by the local_date coalesce + `_resolve_user_timezone`. Follow-ups noted, not done here: `User.timezone` is not validated as an IANA name anywhere (a typo would 500 every summary request for that user via `func.timezone`); archival_repository still buckets archived days in UTC, so archive/live merge keys will disagree once archival is enabled.
- rebased_note_2:            Rebased 2026-08-20 onto upstream d9a64bf. Upstream #1414 (44a268b) added `DataSource.device_type` to get_daily_activity_aggregates' SELECT, GROUP BY and result dict; the wholesale copy shadowed it away, so every activity summary returned `device_type: null` and the frontend fell back to a generic device badge. Re-applied in all three places. get_daily_active_minutes / get_daily_intensity_minutes verified byte-identical to upstream apart from the intended local_date change. Guarded by backend/tests/test_ow_patches_column_drift.py.
- local_patch_file:          ow-patches/local/fix-activity-summary-utc-bucketing.py

---

## fix-garmin-connect-activity-hr-samples

- patch_id:                  fix-garmin-connect-activity-hr-samples
- status:                    local_only
- upstream_url:              https://github.com/the-momentum/open-wearables
- upstream_issue_or_pr:      null
- file:                      backend/app/services/providers/garmin_connect/workouts.py, backend/app/services/providers/garmin_connect/client.py
- symbol:                    GarminConnectWorkouts.load_data + GarminConnectClient.get_activity_details
- what_we_changed:           After saving each Garmin Connect workout, fetch `client.get_activity_details(activity_id)` and persist its `activityDetailMetrics` HR column as additional `heart_rate` time-series samples. The daily HR endpoint is 2-min sampled and undersamples workout peaks (e.g. May 3 trail run reported max 186 by Garmin but stored max 179). Skips workouts with no HR or under 5 minutes; per-activity errors are caught so one bad activity can't poison the sync.
- retire_when:               GarminConnectWorkouts.load_data calls a per-activity HR-detail endpoint and persists per-second (or sub-minute) heart_rate samples for each workout. Marker: presence of `get_activity_details` (or `activityDetailMetrics`) anywhere in backend/app/services/providers/garmin_connect/.
- upstream_equivalent_check: backend/app/services/providers/garmin_connect/::activityDetailMetrics
- rebased_note:              2026-08-29: WIDENED from HR-only to the full webhook-parity metric set, and GATED. The activity-details response already being fetched carries 26 columns; only `directHeartRate` was read. It now persists the same eight series the official webhook provider does, driven by garmin_connect/coverage.py::ACTIVITY_SAMPLE_SERIES which mirrors garmin/coverage.py one-for-one — so the two Garmin providers agree on what a workout sample set contains. Zero additional requests: same response, more columns. ALSO now honours `settings.ingest_workout_samples` like garmin and strava; this provider previously ignored that platform flag, which is why it accumulated ~214k rows from 94 activities against a flag documented as "significantly increases DB storage" and defaulting to False. NOTE the >0 guard is applied only to heart rate — latitude, longitude, elevation and air_temperature are legitimately negative or zero, so a blanket filter would drop the southern hemisphere, sea level and freezing conditions.
- fork_rule_violation:       ⚠ This patch targets `garmin_connect/`, which is FORK-OWNED — FORK.md §2 says never patch a file the fork owns, because it buys every shadowing hazard and none of the conflict benefit. Same for fix-garmin-connect-rate-limit-backoff. Both should be inlined into the provider source; deliberately NOT done in this change to keep a feature PR separate from a refactor, but it is the reason `workouts.py` and `client.py` contain none of this logic.
- local_patch_file:          ow-patches/local/fix-garmin-connect-activity-hr-samples.py

---

## fix-sleep-summary-utc-bucketing

- patch_id:                  fix-sleep-summary-utc-bucketing
- status:                    local_only
- upstream_url:              https://github.com/the-momentum/open-wearables
- upstream_issue_or_pr:      null
- file:                      backend/app/repositories/event_record_repository.py
- symbol:                    EventRecordRepository.get_sleep_summaries + EventRecordRepository._get_sleep_sessions
- what_we_changed:           When EventRecord.zone_offset is NULL (which is the common case for Garmin Connect / Ultrahuman sync paths), upstream falls back to UTC for the `local_sleep_date` bucketing. Replace the fallback with `(end_datetime AT TIME ZONE user.timezone)::date` so a Sunday-morning Brisbane wake doesn't land on the previous UTC day. When user.timezone is also unset, falls through to UTC (= upstream behaviour) so disabling the patch is safe.
- rebased_note:              Rebased 2026-07-26 onto merged upstream. Upstream rewrote get_sleep_summaries (#1257 provider grouping + per-session `sessions` breakdown; #1259 physio LATERAL producing avg_hr/avg_hrv_sdnn/avg_hrv_rmssd/avg_resp/avg_spo2) — the stale wholesale copy dropped ALL of it (re-nulling the physio metrics, the same failure that retired fix-hrv-nightly-aggregate). Now upstream's current body with ONLY the local_sleep_date zone_offset-first / user.timezone-fallback / UTC-fallback swapped. ALSO extended to replace _get_sleep_sessions with the identical bucket, so the sessions key matches the summary key for NULL-zone_offset providers (else `sessions` came back empty for Garmin Connect / Ultrahuman).
- retire_when:               EventRecordRepository.get_sleep_summaries falls back to a non-UTC source when zone_offset is null (i.e. uses user.timezone or any other timezone-aware mechanism for the wake-date bucket).
- upstream_equivalent_check: backend/app/repositories/event_record_repository.py::func.timezone
- rebased_note_3:            2026-09-13: audited against upstream 53de57ca — KEEP AS-IS. check_upstream.py flagged `dad8b3be` (#1540) as shadow risk, but its only change to this file is one line in `_build_creation` (`original_source_name`); neither replaced method changed. Both bodies re-diffed: the local_sleep_date coalesce (+ `_resolve_user_timezone`) is the only difference; physio LATERAL, provider grouping, device_type in all four places, and the 4-tuple sessions join key are intact.
- rebased_note_2:            Rebased 2026-08-20 onto upstream d9a64bf. Same #1414 `device_type` regression as fix-activity-summary-utc-bucketing, in four places (subquery SELECT + GROUP BY, outer SELECT, result dict) plus a stale docstring. Re-applied. NOTE `_get_sleep_sessions` must NOT gain device_type: the summary-side join key is the 4-tuple (sleep_date, provider, source, device_model), and adding it to one side only would empty every `sessions` list. Upstream's #1259 physio LATERAL and #1257 provider grouping verified intact. Guarded by backend/tests/test_ow_patches_column_drift.py.
- local_patch_file:          ow-patches/local/fix-sleep-summary-utc-bucketing.py

---

## fix-health-score-source-priority

- patch_id:                  fix-health-score-source-priority
- status:                    local_only
- upstream_url:              https://github.com/the-momentum/open-wearables
- upstream_issue_or_pr:      null
- file:                      backend/app/repositories/health_score_repository.py, backend/app/models/health_score.py
- symbol:                    HealthScoreRepository.get_with_filters
- what_we_changed:           When `fill_missing_sleep_scores_task` finds two sleep records for the same night (Garmin + Ultrahuman), it persists two `provider='internal'` scores — one per underlying sleep_record_id. Dedupe at read time: group by (local-date in user.timezone, category), keep the score whose underlying sleep record has the highest-priority source. Resilience/recovery scores without a sleep_record_id pass through untouched. Pagination applied after dedup so total_count reflects what consumers see. No-op when caller filters by `provider`.
- retire_when:               HealthScoreRepository.get_with_filters returns at most one score per (local-date, category) when multiple providers have records for the same night, OR upstream offers an explicit dedupe option.
- upstream_equivalent_check: backend/app/repositories/health_score_repository.py::provider_order
- rebased_note_2:            Rebased 2026-08-20. Two correctness fixes, neither caused by upstream drift (get_with_filters is byte-identical to baseline). (1) The dedup ranked on `DataSource.source`, which is free-form (values like `apple_health_sdk` or `com.apple.health.<UUID>`), via the STRICT `ProviderName()` constructor — so every non-canonical row raised, scored 99, and the winner was arbitrary. Now selects the canonical `DataSource.provider` column (added upstream in #1414) and falls back to `ProviderName.from_source_string`, mirroring upstream's own `_filter_by_priority`. It only ever worked because garmin_connect/ultrahuman happen to write source == provider_name. (2) The bucket key did `recorded_at.astimezone(user_tz).date()`, but fill_missing_sleep_scores_task stores an ALREADY-LOCAL datetime wearing a UTC label, so the offset was applied twice — shifting a night backwards for negative offsets. Now uses `.date()` directly for tz-aware values, converting only naive ones.
- rebased_note_3:            2026-08-29: HARD-BROKEN by the merge and fixed. Upstream #1462 (b8f4cfce, Whoop /v2/cycle) renamed `health_score.sleep_record_id` to `event_record_id` (model, schema, column, plus migration dc5ac28c4b94 and index uq_health_score_sleep_record -> uq_health_score_event_record). The patch still referenced the dead attribute in the unconditional outerjoin, so `GET /users/{id}/health-scores` raised AttributeError for EVERY request — 14 tests failed. Renamed both references. ALSO added a `category == SLEEP` gate: the rename widened the FK's meaning, and Whoop now sets it on every per-workout STRAIN score to distinguish those from the per-day cycle strain, so the old "has a record id => dedupe it" rule would have collapsed a user's three Whoop workouts into one — silent data loss. Pre-rename only sleep writers set the column (fill task, Apple HealthKit, Polar), so the gate reproduces this patch's original scope exactly rather than inheriting the widened one. `backend/app/models/health_score.py` added to `file:` above so check_upstream.py flags model drift next time — it was blind to this because only the repository file was tracked, and test_ow_patches_column_drift.py only inspects `DataSource.*` references, not `HealthScore.*`. Verified #1484 does NOT satisfy retire_when: it fixes a different duplicate (two internal writers disagreeing on the recorded_at convention for the SAME session); the fill task still emits one internal score per sleep EventRecord with no priority filter, so Garmin+Ultrahuman on one night still yields two rows.
- audit_note:                2026-09-13 vs 53de57ca — KEEP. health_score_repository.py and models/health_score.py untouched upstream in the range.
- local_patch_file:          ow-patches/local/fix-health-score-source-priority.py

---

## fix-summary-timezone-echo

- patch_id:                  fix-summary-timezone-echo
- status:                    local_only
- upstream_url:              https://github.com/the-momentum/open-wearables
- upstream_issue_or_pr:      null
- file:                      backend/app/schemas/responses/activity/summaries.py, backend/app/services/summaries_service.py
- symbol:                    SummariesService.get_activity_summaries (timezone field on each ActivitySummary)
- replacement_kind:          decorate
- what_we_changed:           Echo `user.timezone` as a `timezone` field on each ActivitySummary so the frontend's display-tz selector knows which IANA zone the daily-bucket dates anchor to. Sleep already does this via fix-sleep-timezone. The schema field is added in source (structural); only the population is toggleable from apply.py.
- rebased_note:              Rebased 2026-07-26. Previously rode inside the wholesale get_activity_summaries replacement; now applied as a standalone one-line population (`summary.timezone = user_tz`) in the get_activity_summaries DECORATOR in apply.py, independent of fix-calories-total-mislabelled. No longer depends on a full method reimplementation.
- retire_when:               ActivitySummary response includes a non-null timezone hint when user.timezone is set (or upstream provides an equivalent way for the frontend to know what timezone the daily-bucket dates are anchored to).
- upstream_equivalent_check: backend/app/schemas/responses/activity/summaries.py::timezone: str | None
- local_patch_file:          ow-patches/local/fix-summary-timezone-echo.py

---

## fix-active-minutes-broken

- patch_id:                  fix-active-minutes-broken
- status:                    retired
- retired_in:                upstream #1242 "active minutes as a new series type" (commit 76ffff4). Marked retired 2026-07-26 against upstream/main; NOT YET MERGED into this fork (baseline 06a6435). Behavioral retirement lands with the upstream merge — see retirement_note.
- upstream_url:              https://github.com/the-momentum/open-wearables
- upstream_issue_or_pr:      null
- file:                      backend/app/services/summaries_service.py
- symbol:                    SummariesService.get_activity_summaries
- what_we_changed:           Derive ActivitySummary.active_minutes from intensity_minutes.{light,moderate,vigorous} (HR-based, intraday) when present, instead of the per-minute step bucket which collapses to ~1 for providers that store steps as a single daily total.
- retire_when:               ActivitySummary.active_minutes equals intensity_minutes.light + moderate + vigorous when HR-based intensity is available, OR upstream uses a different active-minutes signal that doesn't collapse to 1 for daily-total step providers.
- retirement_note:           Superseded by upstream #1242 (76ffff4): SeriesType.active_time ("Provider-reported daily active time", minutes) is persisted for Garmin/Oura/Polar/Ultrahuman, aggregated as active_time_minutes, and get_activity_summaries now prefers it over the step heuristic; independently the repo excludes daily-total step rows from the per-minute bucket (data_point_series_repository.py `is_daily_total.isnot(True)`, ~L668) so the fallback returns null instead of collapsing to 1 — satisfying the second retire_when clause. Keeping our override is strictly worse: our intensity-band derivation now SHADOWS upstream's more authoritative active_time signal (the composed get_activity_summaries never reads active_time_minutes). CAVEAT — retired ahead of the merge: the PATCHES_ENABLED flag is False, but active_minutes is currently still computed by the composed fix-calories-total-mislabelled base_impl (they share the wholesale get_activity_summaries replacement), so the flag flip is bookkeeping until (a) upstream/main is merged and (b) fix-calories-total-mislabelled is rebased to a decorator over upstream's get_activity_summaries. Run the pytest verification at that point, not now. garmin_connect (fork-only) does not emit SeriesType.active_time, so post-merge its active_minutes falls to the step path which now returns null (honest) rather than 1 — accepted regression.
- upstream_equivalent_check: active_mins = light + moderate + vigorous
- local_patch_file:          ow-patches/local/fix-active-minutes-broken.py

---

## fix-garmin-connect-rate-limit-backoff

- patch_id:                  fix-garmin-connect-rate-limit-backoff
- status:                    retired
- replacement_kind:          wholesale-replace
- retirement_note:           2026-09-13: RETIRED INTO SOURCE. Both target files are fork-only (`garmin_connect/` does not exist upstream), so per FORK.md §2 this should never have been a patch — it bought every shadowing hazard and no upstream-conflict benefit. The hazard bit: e88508db (2026-08-29) added `save_vo2max_for_range` + `"vo2_max"` to the real `load_and_save_all`, and this patch's wholesale copy silently shadowed it, so garmin_connect VO2max never synced in production for two weeks (no error, no failing test — the rate-limit tests stubbed only the five per-day methods). Found by the 2026-09-13 reconcile audit. Now: `GarminConnectRateLimitError`, the classifier helpers, the Redis cooldown (`cooldown_remaining` / `_record_rate_limit` / `_clear_rate_limit`), `_blocked_for`, `_login`, `_get_api`, `_call_with_reauth` live in `client.py`; the abort-on-`GarminConnectClientError` + cooldown pre-flight `load_and_save_all` lives in `data_247.py` (with the VO2max block restored). Behaviour unchanged otherwise. `tests/providers/garmin_connect/test_garmin_connect_rate_limit.py` now targets the client module (its `patch_module` fixture name is kept). Flag set False, removed from `_STANDALONE_PATCHES` and `_EXPECTED_PATCHED`. The patch file is kept for history and is no longer loaded.
- upstream_url:              https://github.com/the-momentum/open-wearables
- upstream_issue_or_pr:      null
- file:                      backend/app/services/providers/garmin_connect/client.py, backend/app/services/providers/garmin_connect/data_247.py
- symbol:                    GarminConnectClient._login + ._get_api + ._call_with_reauth, GarminConnect247Data.load_and_save_all
- what_we_changed:           Stop the credential-based Garmin Connect sync from self-inflicting an IP-level rate-limit ban. (1) Added `GarminConnectRateLimitError` and classify 429 / Cloudflare-challenge / "all login strategies exhausted" failures as rate-limiting rather than auth failures — `_call_with_reauth` no longer re-logs-in on them (upstream's auth-marker list matched "403" and "login", so a Cloudflare 403 cost two login storms instead of one). (2) `_get_api` refuses to attempt login while blocked, using an in-process `_blocked_until` plus a Redis cooldown key, so the remaining ~149 iterations of a run fail instantly without network I/O. (3) The Redis cooldown escalates geometrically per consecutive strike (30m → 1h → 2h → 4h, capped 6h, reset on success) so the hourly beat schedule stops re-hammering. (4) `load_and_save_all` pre-flight-checks the cooldown, breaks out of BOTH loops on the first rate-limit instead of swallowing it per (date, data_type), and re-raises so the run is recorded failed rather than silently `partial` with zero records. Genuinely transient errors retry with bounded exponential backoff + jitter, honouring `Retry-After`. Non-rate-limit per-day errors are still swallowed and logged exactly as before.
- why:                       `load_and_save_all` loops ~30 dates × 5 data types with a blanket `except Exception` that cannot tell "no stress data today" from "we are 429'd". Because `_get_api` only assigns `self._api` after a *successful* login, a failed login left it `None` and every one of the ~150 iterations re-attempted a full login — and the underlying `garminconnect` client tries five strategies per login, sleeping ~16–20s inside the portal strategy. That is up to ~750 auth requests per run, hourly, with overlapping runs. Observed 2026-08-20: every hourly run finishing `partial`, `garmin_connect` data stuck since 2026-08-03, logs a solid wall of `429 — IP rate limited by Garmin` and `HTTP 403 (Cloudflare bot challenge)`. Same failure class as the Ultrahuman refresh bug: an unrecoverable auth error treated as a recoverable per-day error.
- retire_when:               GarminConnectClient distinguishes rate-limit/WAF rejections from ordinary auth failures and stops re-attempting login once blocked, AND load_and_save_all aborts the run instead of continuing through every remaining (date, data_type) pair.
- upstream_equivalent_check: backend/app/services/providers/garmin_connect/::GarminConnectRateLimitError
- rebased_note:              2026-08-20: this patch was SILENTLY INERT on first landing. Its id was added to PATCHES_ENABLED but not to `_STANDALONE_PATCHES` in apply.py, and apply_patches() iterates the tuple, not the flag dict — so it never installed. Its own tests passed because the fixture called install() directly. Fixed by adding it to `_STANDALONE_PATCHES`; the test fixture now uses the already-installed module instead of loading a second copy. Guarded by backend/tests/test_ow_patches_installed.py::TestRegistryConsistency.
- rebased_note_2:            2026-08-20 (second pass): the original fix only aborted the run on GarminConnectRateLimitError. Real-world escalation went 429 -> IP block -> ACCOUNT_LOCKED, and after the lock Garmin returns a misleading `401 Unauthorized (Invalid Username or Password)` — correctly classified as an AUTH failure, so the per-day loop swallowed it and kept re-attempting login, keeping the lock alive. Now (a) `_is_account_locked` recognises ACCOUNT_LOCKED / generalLoginAccountLocked and applies the same escalating cooldown as a rate limit, raising an error that names the remedy (password reset at garmin.com), and (b) load_and_save_all aborts on ANY GarminConnectClientError, not just the rate-limit subclass — a credential problem will still be true on the next (date, data_type) pair. Genuinely per-day errors are still swallowed.
- local_patch_file:          ow-patches/local/fix-garmin-connect-rate-limit-backoff.py

---

## fix-provider-prefix-shadowing

- patch_id:                  fix-provider-prefix-shadowing
- status:                    upstream_candidate
- replacement_kind:          standalone
- upstream_url:              https://github.com/the-momentum/open-wearables
- upstream_issue_or_pr:      null
- file:                      backend/app/schemas/enums/provider.py
- symbol:                    ProviderName.from_source_string
- what_we_changed:           Match provider values LONGEST-FIRST instead of in enum declaration order, and normalise ` ` / `-` to `_` before matching. Upstream iterates `for provider in cls` and returns the first value that is a substring of the source, so `GARMIN = "garmin"` (declared line 9) always beat `GARMIN_CONNECT = "garmin_connect"` (line 10) — `"garmin" in "garmin_connect"` is True, making GARMIN_CONNECT unreachable through this function. Generic flaw: any provider value that is a prefix of another shadows it.
- why:                       The result is PERSISTED, not just displayed. `infer_provider_from_source` delegates here and runs on the write path in event_record_repository.py:57/:190 and data_point_series_repository.py:181/:341 (line numbers as of 2026-09-13), so every data_source row for garmin_connect stored `provider='garmin'`. That surfaced as `provider: "garmin"` alongside `source: "garmin_connect"` on the summaries endpoints, and — worse — provider-priority resolution (summaries_service.py `_filter_by_priority`, plus fix-health-score-source-priority) ranked garmin_connect in GARMIN's slot, so the wrong source could win a de-duplication against Ultrahuman for the same night.
- structural_note:           Upstream's own test `backend/tests/schemas/test_provider_name.py` asserts `("garmin_connect", ProviderName.GARMIN)` — it codifies the bug. That case is changed to GARMIN_CONNECT with an inline FORK DIVERGENCE comment. This is a STRUCTURAL edit to an upstream test file and will surface as a git conflict on future merges; that is intended, so the divergence gets re-examined rather than silently reverted.
- migration:                 backend/migrations/versions/2026_08_20_0600-c4d5e6f7a8b9_fix_garmin_connect_provider_mislabel.py repairs rows already written. Scoped to rows whose `source` identifies garmin_connect, so official-garmin rows are untouched, and skips rows that would collide with uq_data_source_identity.
- retire_when:               ProviderName.from_source_string resolves "garmin_connect" to ProviderName.GARMIN_CONNECT. Marker: any longest-match / sorted-by-length logic or an explicit alias table inside from_source_string.
- upstream_equivalent_check: backend/app/schemas/enums/provider.py::key=lambda
- audit_note:                2026-09-13 vs 53de57ca — KEEP. Upstream 02deb366 only added `WITHINGS = "withings"`; from_source_string is still declaration-order first-substring. "withings" is neither prefix nor superstring of another value, so the longest-first patch handles it unchanged. test_provider_name.py FORK DIVERGENCE case intact; no new upstream cases.
- local_patch_file:          ow-patches/local/fix-provider-prefix-shadowing.py

---

## celery-late-acks

- patch_id:                  celery-late-acks
- status:                    local_only
- replacement_kind:          structural
- upstream_url:              https://github.com/the-momentum/open-wearables
- file:                      backend/app/integrations/celery/core.py, backend/app/integrations/celery/tasks/sync_vendor_data_task.py
- symbol:                    create_celery (conf.update) + sync_vendor_data (@shared_task decorator)
- what_we_changed:           PER-TASK `@shared_task(acks_late=True)` on `sync_vendor_data`, `broker_transport_options["visibility_timeout"] = 6h`, and `worker_prefetch_multiplier=1`. NOT set globally: 7d3aa89d originally set `task_acks_late` + `task_reject_on_worker_lost` in `create_celery`; 7fcbfb6b moved to per-task because a global flag opts in every task that never proved itself idempotent, and `task_reject_on_worker_lost` only matters on the prefork pool (this worker runs `--pool=threads`). `worker_prefetch_multiplier=1` is REQUIRED with late acks: at the default of 4 a worker holds three unstarted messages unacked for the whole duration of the running one, and they can exceed `visibility_timeout` and be redelivered to a second worker. (Entry corrected 2026-09-13 — it described the 7d3aa89d state.)
- why:                       Celery's default acks a message on RECEIPT, before the task runs. A long historical backfill killed by a pod rollout is therefore lost outright — no redelivery — and its `sync:status:run:*` Redis record is frozen at `in_progress` until the ~24h TTL. That is what presents in the UI as a "hanging sync": the run is not slow, it no longer exists. Observed 2026-08-29 — two year-long backfills (ultrahuman `pull_3c24a7708dd343c7`, garmin_connect `pull_82a3a6ce18c64874`) started 05:56Z, were orphaned by one of that day's four deploys, and left no trace in any queue: all four queues at depth 0, `unacked` empty, `inspect active/reserved` empty.
- structural_note:           This is a STRUCTURAL edit to an upstream file, not a runtime patch. Celery config is read once at worker startup, so `apply.py` cannot reach it — and per FORK.md §2 a patch would buy shadowing hazard with no conflict benefit. It will surface as a git conflict on future merges; that is intended.
- safety:                    Late acks are only safe for idempotent tasks. They are safe here because ingest is upsert-based (`ON CONFLICT` on `uq_data_point_series_source_type_time`), so a redelivered task re-runs without duplicating rows. **`visibility_timeout` MUST stay above the longest task**: with late acks the message is unacked for the task's whole duration, and if the timeout elapses first Redis redelivers it to another worker and the same backfill runs twice concurrently — exactly how garmin_connect got IP rate-limited and then account-locked. Celery's default is 1 hour; a year-long backfill exceeds it.
- deliberately_not_set:      `task_time_limit` / `task_soft_time_limit`. The worker runs `--pool=threads` (`scripts/start/worker.sh`) and Celery enforces time limits only on the prefork pool, so setting them would be inert config that reads as protection. Bound the provider HTTP calls instead, or move to prefork.
- deployment:                Pairs with `terminationGracePeriodSeconds: 600` on the celery-worker Deployment (homelab repo). At the previous 30s a backfill had no chance to drain — the 90-day Ultrahuman backfill alone takes ~3m20s.
- known_gap_resolved:        2026-09-13: upstream #1448 (7bc9c27e / 46d035e5) is merged. `close_stale_sync_runs_task.close_stale_sync_runs` runs every `sync_run_sweep_interval_seconds` (1800s), marks runs older than `sync_run_stale_after_hours` (2h) as `SyncStatus.STALE` after a Redis liveness pre-check (`last_event_at`), so an orphaned run is no longer visible until its TTL. `gc_stuck_backfills` was removed upstream (#1591). Historical: a fork reaper was written on 2026-08-30 and deleted on discovering it duplicated #1448.
- dead_metadata:             `sync_vendor_data_task.py` stamps `"task_id": _current_task_id()` into the `started` event metadata (FORK DELTA comment says it is for matching a cancel request to the Celery task and for liveness). Nothing consumes it: cancellation is a Redis flag keyed by run_id (`sync_cancel_service.request_cancel`), and the stale sweep uses the event timestamp. Harmless; either wire it or drop the delta to shrink the reconcile surface.
- crash_loop_caveat:         Late acks assume the task eventually succeeds. A task that fails DETERMINISTICALLY is never acked and is redelivered every `visibility_timeout` forever — Celery counts retries, not redeliveries, so nothing gives up. Observed 2026-08-30: a 1-year backfill OOM-killed the worker (exitCode 137) ~3m in, was redelivered at exactly +6h, and OOM'd again, orphaning another run record each cycle. Mitigated by `historical-sync-chunking` below; the ceiling itself is still unbuilt.
- retire_when:               Upstream sets `acks_late=True` on `sync_vendor_data` or `task_acks_late` in `create_celery` (or documents an equivalent restart-safety story). Checked 2026-09-13 against 53de57ca: upstream's `sync_vendor_data` is still a bare `@shared_task`.

---

# Frontend Patches (Source Edits)

These changes live directly in `frontend/src/` and are **not toggleable** via
`apply.py` — the frontend is built once and served as static assets, so a
runtime monkey-patch wouldn't make sense. They're listed here for the same
reason as the backend patches: institutional memory of where we've diverged
from upstream so future developers (and `check_upstream.py` reviews of the
companion backend changes) have the full picture.

To revert a frontend patch, revert the source files via `git checkout
upstream/main -- <files>`. There's no flag to flip.

---

## frontend-display-timezone

- patch_id:           frontend-display-timezone
- status:             local_only
- replacement_kind:   structural
- upstream_url:       https://github.com/the-momentum/open-wearables
- files:
  - frontend/package.json (added `date-fns-tz`)
  - frontend/src/lib/dates.ts                       (new helper module)
  - frontend/src/contexts/display-timezone.tsx       (new context)
  - frontend/src/components/common/timezone-selector.tsx (new selector)
  - frontend/src/components/user/sleep-section.tsx   (formatInTz)
  - frontend/src/components/user/activity-section.tsx (comment only — this
    section renders daily-bucket calendar dates via parseApiDate and
    deliberately does NOT use formatInTz; see what_we_changed below)
  - frontend/src/components/user/scores-section.tsx  (formatInTz)
  - frontend/src/components/user/workout-section.tsx (formatInTz)
  - frontend/src/components/user/profile-section.tsx (timezone field on Edit form)
  - frontend/src/lib/utils/timeseries.ts             (prepareHrChartData accepts tz)
  - frontend/src/lib/api/types.ts                    (UserRead/UserUpdate.timezone, SleepSummary.timezone/start_time_local/end_time_local, ActivitySummary.timezone/basal_calories_kcal)
  - frontend/src/routes/_authenticated/users/$userId.tsx (DisplayTimezoneProvider + TimezoneSelector mounted)
- what_we_changed:    Two distinct timezones in the dashboard:
  1. **User Timezone** (User.timezone IANA, settable from the profile edit
     dialog or PATCH /users/{id}). Anchors backend daily-bucket dates.
  2. **Display Timezone** (ephemeral, view-only). DropdownMenu picker at the
     top of the user dashboard. **Defaults to the viewed user's User.timezone**,
     falling back to UTC only when that is unset. Persisted in localStorage
     keyed per user_id — but only an EXPLICIT pick is stored, so the default
     keeps tracking User.timezone if it later changes. Drives `formatInTz(...)`
     for every UTC datetime rendered in sleep / activity / scores / workout
     sections plus the HR-during-sleep and HR-during-workout chart axes.
     Does NOT modify data.
  Calendar dates from daily-bucketed summaries (e.g. ActivitySummary.date
  "2026-05-03") are deliberately rendered in UTC anchor so the day label
  ("May 3") stays stable as the developer toggles the display tz.
- fix_note:           2026-08-29: the display tz previously defaulted to UTC
  unconditionally, and `DisplayTimezoneProvider` was never passed the user's
  timezone at all. So a Brisbane user's dashboard opened with every timestamp
  10 hours out until they touched the picker — a 23:58 bedtime rendered as
  13:58, and `computeSleepStats`'s avgBedtime (lib/utils/sleep.ts) averaged UTC
  wall-clock minutes. The per-record maths was always correct; only the seed
  zone was wrong, which is why it looked like a formatting bug rather than a
  default-value one. `readStoredTz` now returns `string | null` so "never
  picked" is distinguishable from "explicitly picked UTC", and the effective
  zone is DERIVED (`override ?? userTimezone ?? UTC`) rather than stored — so it
  updates itself when the async user query resolves. The selector's reset item
  now reads "Reset to {userTimezone}" accordingly.
- retire_when:        Upstream ships a similar two-timezone model (one stored,
  one display) — would surface as `User.timezone` in upstream + a display-tz
  context provider on the user dashboard.
- discovery:          `grep -r 'formatInTz\|DisplayTimezoneProvider\|date-fns-tz' frontend/src/`

## historical-sync-chunking

- patch_id:                  historical-sync-chunking
- status:                    local_only
- replacement_kind:          structural
- upstream_url:              https://github.com/the-momentum/open-wearables
- file:                      backend/app/services/providers/base_strategy.py, backend/app/integrations/celery/tasks/sync_vendor_data_task.py, backend/app/api/routes/v1/sync_data.py
- symbol:                    BaseProviderStrategy.start_historical_sync, sync_vendor_data, cancel_sync_run (new route)
- what_we_changed:           `start_historical_sync` now splits the window into `HISTORICAL_CHUNK_DAYS` (30) chunks and dispatches them as a sequential Celery `chain` of immutable signatures, instead of one task spanning the whole range. Added an RSS guard (`app/utils/memory_guard.py`) polled per provider, a cooperative cancel flag (`app/services/sync_cancel_service.py`), and `POST /sync/runs/{run_id}/cancel`.
- why:                       Upstream sends the entire range as one task. For a year that is one message holding one SQLAlchemy session across 365 days x 5 per-day endpoints plus every activity in the window; it OOM-killed the worker on 2026-08-30 and, because of `celery-late-acks`, was redelivered every 6h to OOM again in an unbounded crash loop. Chunking bounds memory and wall-clock by construction: every chunk finishes far inside `visibility_timeout`, a failure costs one chunk, and completed chunks stay committed.
- why_chained_not_parallel:  Request volume is the binding constraint on the REST providers (FORK.md §2). Firing 13 concurrent chunks at Garmin is precisely what got this account IP rate-limited and then locked. `.si()` immutable signatures because each chunk takes explicit kwargs and must not receive the previous chunk's return value positionally.
- why_not_celery_settings:   `worker_max_memory_per_child` / `worker_max_tasks_per_child` recycle a *child process* and are enforced only on the prefork pool. This worker runs `--pool=threads`, so both are inert here — the same reason `celery-late-acks` declines to set `task_time_limit`. There is no Python equivalent of Go's GOMEMLIMIT; `resource.setrlimit(RLIMIT_AS)` caps address space process-wide and would surface as a MemoryError from an arbitrary thread. Hence an explicit RSS checkpoint instead.
- why_flag_not_revoke:       `control.revoke(terminate=True)` sends SIGTERM to the executing process. On a threads pool that kills the worker and every other task sharing it — the same blast radius that made one OOM take down two syncs. Cancellation is therefore cooperative, mirroring `set_garmin_cancel_flag`.
- upstream_overlap:          Checked before building (2026-08-30). Upstream chunks at the *request* level only (`oura/data_247.py` `_CHUNK_DAYS = 30`, `suunto/data_247.py` `_fetch_in_chunks`) to satisfy provider API window caps — inside a single task, so it addresses neither memory nor redelivery. Upstream PR #1448 adds the stale-run sweep and `emit_sync_cancelled` but **no cancel endpoint** and nothing on chunking or memory.
- structural_note:           STRUCTURAL edits to upstream files. `base_strategy.py` was previously identical to upstream, so this creates new divergence that will conflict on merge; that is intended. `sync_cancel_service.py` and `memory_guard.py` are new fork-owned modules, deliberately NOT additions to `sync_status_service.py`, because #1448 rewrites large parts of that file and a new-file add reconciles more cleanly than a conflict inside a rewritten module.
- reconcile_watch:           Upstream PR #1501 refactors `load_and_save_all` heavily (`Sync247Result`, `Sync247Run.step`, `resolve_window`). `fix-garmin-connect-rate-limit-backoff` wholesale-replaces that exact method, so it will silently shadow #1501 on merge. Diff it before trusting it.
- reconcile_note:            2026-09-13 (upstream 53de57ca): #1448 landed (`SyncRun` table, `emit_sync_*` renames, `run_status_from`, `try_record_data_types`, stale sweep) and #1591 REMOVED the Garmin backfill cancel/retry endpoints and `gc_stuck_backfills`. The fork's `POST /sync/runs/{run_id}/cancel` and `SyncCancelledError` branch were re-applied on top; the cancel branch now calls `emit_sync_cancelled(..., scope=sync_scope)` (upstream's name, was the fork alias `cancelled`). base_strategy.py chunking auto-merged (upstream only added `webhook_subscription_per_user`). retire_when still unmet: upstream sends one task per historical sync and has no pull-provider cancel endpoint.
- retire_when:               Upstream chunks historical syncs at the task level (marker: more than one `sync_vendor_data` message per `start_historical_sync` call) AND exposes a cancel endpoint for pull-provider runs.

---

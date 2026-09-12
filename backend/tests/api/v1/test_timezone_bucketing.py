"""Regression tests for timezone-aware date bucketing in summary endpoints.

These tests lock in the expected bucketing behaviour for users east (and west)
of UTC so that the merge of upstream's zone_offset-based bucketing approach
with our user.timezone fallback cannot silently regress.

Three orthogonal cases are covered for each summary type:
  A. zone_offset set on the data row  → upstream's expression fires
  B. zone_offset NULL, user.timezone set  → our patch's fallback fires
  C. zone_offset NULL, user.timezone NULL  → UTC fallback (upstream parity)

Concrete scenario used throughout
----------------------------------
A Brisbane user (UTC+10, no DST) goes for a run on the morning of
Sunday 2026-05-03 local time. The UTC timestamps of their samples all
fall on Saturday 2026-05-02 UTC (e.g. a 07:30 local start = 21:30 UTC
the previous day).

With correct bucketing the activity card for 2026-05-03 shows the run data.
Without correct bucketing (UTC fallback) the data lands on 2026-05-02 and
the 2026-05-03 card appears empty.

Similarly, a sleep session ending at 06:11 Brisbane time on 2026-05-04
has a UTC end_datetime of 2026-05-03 20:11.  The wake-date (the "date" field
on a SleepSummary) should be 2026-05-04, not 2026-05-03.
"""

from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import (
    ApiKeyFactory,
    DataPointSeriesFactory,
    DataSourceFactory,
    EventRecordFactory,
    SeriesTypeDefinitionFactory,
    UserFactory,
)
from tests.utils import api_key_headers

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

BRISBANE_TZ = "Australia/Brisbane"  # UTC+10, no DST
LONDON_TZ = "Europe/London"  # UTC+0/+1 — used for west-of-UTC variant

# The "Sunday morning run" timestamps
# Local (Brisbane):  2026-05-03 07:30 → 09:00
# UTC:               2026-05-02 21:30 → 23:00  (Saturday UTC)
RUN_UTC_START = datetime(2026, 5, 2, 21, 30, 0, tzinfo=timezone.utc)
RUN_UTC_END = datetime(2026, 5, 2, 23, 0, 0, tzinfo=timezone.utc)
RUN_LOCAL_DATE = "2026-05-03"  # expected bucket for Brisbane user
RUN_UTC_DATE = "2026-05-02"  # bucket without timezone correction

# The "Sunday morning wake" timestamps for sleep
# Local (Brisbane):  sleep ends 2026-05-04 06:11
# UTC:               2026-05-03 20:11  (Saturday UTC)
SLEEP_START_UTC = datetime(2026, 5, 3, 11, 54, 0, tzinfo=timezone.utc)
SLEEP_END_UTC = datetime(2026, 5, 3, 20, 11, 0, tzinfo=timezone.utc)
SLEEP_WAKE_LOCAL_DATE = "2026-05-04"  # correct wake-date for Brisbane
SLEEP_WAKE_UTC_DATE = "2026-05-03"  # wrong — UTC fallback


# ---------------------------------------------------------------------------
# Activity summary bucketing
# ---------------------------------------------------------------------------


class TestActivityBucketingWithZoneOffset:
    """Case A: zone_offset is set on each data point.

    Upstream's bucketing expression uses the per-record zone_offset column.
    The data lives at UTC-Saturday timestamps; with "+10:00" offset it should
    bucket to local-Sunday.
    """

    def test_steps_bucket_to_local_date_via_zone_offset(self, client: TestClient, db: Session) -> None:
        """Steps recorded Saturday UTC but Sunday local → bucket to Sunday."""
        user = UserFactory(timezone=None)  # user.timezone not needed here
        mapping = DataSourceFactory(user=user, source="garmin")
        steps_type = SeriesTypeDefinitionFactory.get_or_create_steps()

        for offset_minutes in (0, 30, 60):
            from datetime import timedelta

            DataPointSeriesFactory(
                mapping=mapping,
                series_type=steps_type,
                value=Decimal("500"),
                recorded_at=RUN_UTC_START + timedelta(minutes=offset_minutes),
                zone_offset="+10:00",
            )

        api_key = ApiKeyFactory()
        response = client.get(
            f"/api/v1/users/{user.id}/summaries/activity",
            headers=api_key_headers(api_key.plain_key),
            params={
                "start_date": "2026-05-03T00:00:00Z",
                "end_date": "2026-05-04T00:00:00Z",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1, (
            f"Expected 1 day bucket (2026-05-03 local) but got: {[r['date'] for r in data['data']]}"
        )
        assert data["data"][0]["date"] == RUN_LOCAL_DATE
        assert data["data"][0]["steps"] == 1500

    def test_steps_do_not_appear_on_wrong_utc_date(self, client: TestClient, db: Session) -> None:
        """With zone_offset set, UTC-Saturday samples must NOT appear on 2026-05-02."""
        user = UserFactory(timezone=None)
        mapping = DataSourceFactory(user=user, source="garmin")
        steps_type = SeriesTypeDefinitionFactory.get_or_create_steps()

        DataPointSeriesFactory(
            mapping=mapping,
            series_type=steps_type,
            value=Decimal("1000"),
            recorded_at=RUN_UTC_START,
            zone_offset="+10:00",
        )

        api_key = ApiKeyFactory()
        response = client.get(
            f"/api/v1/users/{user.id}/summaries/activity",
            headers=api_key_headers(api_key.plain_key),
            params={
                "start_date": "2026-05-02T00:00:00Z",
                "end_date": "2026-05-03T00:00:00Z",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"] == [], "Samples with +10:00 offset should not appear in the UTC-Saturday bucket"


class TestActivityBucketingWithUserTimezone:
    """Case B: zone_offset is NULL, user.timezone is set.

    This is the common case for Garmin Connect and Ultrahuman ingest, which
    do not populate zone_offset.  Our patch falls back to user.timezone.
    """

    def test_steps_bucket_to_local_date_via_user_timezone(self, client: TestClient, db: Session) -> None:
        """With zone_offset=NULL and user.timezone=Brisbane, UTC-Saturday → local-Sunday."""
        user = UserFactory(timezone=BRISBANE_TZ)
        mapping = DataSourceFactory(user=user, source="garmin")
        steps_type = SeriesTypeDefinitionFactory.get_or_create_steps()

        from datetime import timedelta

        for offset_minutes in (0, 30, 60):
            DataPointSeriesFactory(
                mapping=mapping,
                series_type=steps_type,
                value=Decimal("500"),
                recorded_at=RUN_UTC_START + timedelta(minutes=offset_minutes),
                zone_offset=None,
            )

        api_key = ApiKeyFactory()
        response = client.get(
            f"/api/v1/users/{user.id}/summaries/activity",
            headers=api_key_headers(api_key.plain_key),
            params={
                "start_date": "2026-05-03T00:00:00Z",
                "end_date": "2026-05-04T00:00:00Z",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1, (
            f"Expected 1 day bucket (2026-05-03 local via user.timezone) but got: {[r['date'] for r in data['data']]}"
        )
        assert data["data"][0]["date"] == RUN_LOCAL_DATE
        assert data["data"][0]["steps"] == 1500

    def test_steps_do_not_appear_on_wrong_utc_date_user_timezone(self, client: TestClient, db: Session) -> None:
        """UTC-Saturday samples must NOT appear on 2026-05-02 when user.timezone=Brisbane."""
        user = UserFactory(timezone=BRISBANE_TZ)
        mapping = DataSourceFactory(user=user, source="garmin")
        steps_type = SeriesTypeDefinitionFactory.get_or_create_steps()

        DataPointSeriesFactory(
            mapping=mapping,
            series_type=steps_type,
            value=Decimal("1000"),
            recorded_at=RUN_UTC_START,
            zone_offset=None,
        )

        api_key = ApiKeyFactory()
        response = client.get(
            f"/api/v1/users/{user.id}/summaries/activity",
            headers=api_key_headers(api_key.plain_key),
            params={
                "start_date": "2026-05-02T00:00:00Z",
                "end_date": "2026-05-03T00:00:00Z",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"] == [], "Samples should not appear in UTC-Saturday bucket when user.timezone=Brisbane"

    def test_zone_offset_takes_precedence_over_user_timezone(self, client: TestClient, db: Session) -> None:
        """When both zone_offset and user.timezone are set, zone_offset wins.

        A sample with zone_offset="+00:00" on a Brisbane user should bucket to
        the UTC date (2026-05-02), not the Brisbane local date (2026-05-03).
        """
        user = UserFactory(timezone=BRISBANE_TZ)
        mapping = DataSourceFactory(user=user, source="apple")
        steps_type = SeriesTypeDefinitionFactory.get_or_create_steps()

        DataPointSeriesFactory(
            mapping=mapping,
            series_type=steps_type,
            value=Decimal("1000"),
            recorded_at=RUN_UTC_START,
            zone_offset="+00:00",  # explicitly UTC — should override user.timezone
        )

        api_key = ApiKeyFactory()
        response = client.get(
            f"/api/v1/users/{user.id}/summaries/activity",
            headers=api_key_headers(api_key.plain_key),
            params={
                "start_date": "2026-05-02T00:00:00Z",
                "end_date": "2026-05-03T00:00:00Z",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1, "zone_offset=+00:00 should anchor the sample to 2026-05-02, not 2026-05-03"
        assert data["data"][0]["date"] == RUN_UTC_DATE


class TestActivityBucketingUtcFallback:
    """Case C: zone_offset NULL, user.timezone NULL — must fall back to UTC (upstream parity)."""

    def test_steps_bucket_to_utc_date_when_no_timezone(self, client: TestClient, db: Session) -> None:
        """With no timezone anywhere, samples bucket by UTC date."""
        user = UserFactory(timezone=None)
        mapping = DataSourceFactory(user=user, source="garmin")
        steps_type = SeriesTypeDefinitionFactory.get_or_create_steps()

        DataPointSeriesFactory(
            mapping=mapping,
            series_type=steps_type,
            value=Decimal("1000"),
            recorded_at=RUN_UTC_START,
            zone_offset=None,
        )

        api_key = ApiKeyFactory()
        response = client.get(
            f"/api/v1/users/{user.id}/summaries/activity",
            headers=api_key_headers(api_key.plain_key),
            params={
                "start_date": "2026-05-02T00:00:00Z",
                "end_date": "2026-05-03T00:00:00Z",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["date"] == RUN_UTC_DATE


# ---------------------------------------------------------------------------
# Sleep summary (wake-date) bucketing
# ---------------------------------------------------------------------------


class TestSleepBucketingWithZoneOffset:
    """Case A: zone_offset set on the sleep record.

    The sleep ends at UTC 2026-05-03 20:11, which with +10:00 is
    2026-05-04 06:11 local — the correct wake date.
    """

    def test_wake_date_uses_zone_offset(self, client: TestClient, db: Session) -> None:
        user = UserFactory(timezone=None)
        mapping = DataSourceFactory(user=user, source="garmin")

        EventRecordFactory(
            mapping=mapping,
            category="sleep",
            start_datetime=SLEEP_START_UTC,
            end_datetime=SLEEP_END_UTC,
            duration_seconds=int((SLEEP_END_UTC - SLEEP_START_UTC).total_seconds()),
            zone_offset="+10:00",
        )

        api_key = ApiKeyFactory()
        response = client.get(
            f"/api/v1/users/{user.id}/summaries/sleep",
            headers=api_key_headers(api_key.plain_key),
            params={
                "start_date": "2026-05-04T00:00:00Z",
                "end_date": "2026-05-05T00:00:00Z",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1, (
            f"Sleep session should appear on wake date {SLEEP_WAKE_LOCAL_DATE} "
            f"(zone_offset +10:00) but got: {[r['date'] for r in data['data']]}"
        )
        assert data["data"][0]["date"] == SLEEP_WAKE_LOCAL_DATE

    def test_sleep_not_visible_on_wrong_utc_date_zone_offset(self, client: TestClient, db: Session) -> None:
        """With zone_offset=+10:00, session must NOT appear on the UTC wake date (2026-05-03)."""
        user = UserFactory(timezone=None)
        mapping = DataSourceFactory(user=user, source="garmin")

        EventRecordFactory(
            mapping=mapping,
            category="sleep",
            start_datetime=SLEEP_START_UTC,
            end_datetime=SLEEP_END_UTC,
            duration_seconds=int((SLEEP_END_UTC - SLEEP_START_UTC).total_seconds()),
            zone_offset="+10:00",
        )

        api_key = ApiKeyFactory()
        response = client.get(
            f"/api/v1/users/{user.id}/summaries/sleep",
            headers=api_key_headers(api_key.plain_key),
            params={
                "start_date": "2026-05-03T00:00:00Z",
                "end_date": "2026-05-04T00:00:00Z",
            },
        )

        assert response.status_code == 200
        assert response.json()["data"] == []


class TestSleepBucketingWithUserTimezone:
    """Case B: zone_offset NULL, user.timezone set.

    This is the real-world Garmin Connect / Ultrahuman path.  Our patch makes
    the fallback use user.timezone instead of UTC.
    """

    def test_wake_date_uses_user_timezone_when_zone_offset_null(self, client: TestClient, db: Session) -> None:
        """Sleep ending 2026-05-03 20:11 UTC → wake date 2026-05-04 for Brisbane user."""
        user = UserFactory(timezone=BRISBANE_TZ)
        mapping = DataSourceFactory(user=user, source="garmin")

        EventRecordFactory(
            mapping=mapping,
            category="sleep",
            start_datetime=SLEEP_START_UTC,
            end_datetime=SLEEP_END_UTC,
            duration_seconds=int((SLEEP_END_UTC - SLEEP_START_UTC).total_seconds()),
            zone_offset=None,
        )

        api_key = ApiKeyFactory()
        response = client.get(
            f"/api/v1/users/{user.id}/summaries/sleep",
            headers=api_key_headers(api_key.plain_key),
            params={
                "start_date": "2026-05-04T00:00:00Z",
                "end_date": "2026-05-05T00:00:00Z",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1, (
            f"Sleep session should appear on wake date {SLEEP_WAKE_LOCAL_DATE} "
            f"(user.timezone=Brisbane, zone_offset=NULL) but got: "
            f"{[r['date'] for r in data['data']]}"
        )
        assert data["data"][0]["date"] == SLEEP_WAKE_LOCAL_DATE

    def test_sleep_not_visible_on_wrong_utc_date_user_timezone(self, client: TestClient, db: Session) -> None:
        """Session must NOT appear on the UTC date (2026-05-03) when user.timezone=Brisbane."""
        user = UserFactory(timezone=BRISBANE_TZ)
        mapping = DataSourceFactory(user=user, source="garmin")

        EventRecordFactory(
            mapping=mapping,
            category="sleep",
            start_datetime=SLEEP_START_UTC,
            end_datetime=SLEEP_END_UTC,
            duration_seconds=int((SLEEP_END_UTC - SLEEP_START_UTC).total_seconds()),
            zone_offset=None,
        )

        api_key = ApiKeyFactory()
        response = client.get(
            f"/api/v1/users/{user.id}/summaries/sleep",
            headers=api_key_headers(api_key.plain_key),
            params={
                "start_date": "2026-05-03T00:00:00Z",
                "end_date": "2026-05-04T00:00:00Z",
            },
        )

        assert response.status_code == 200
        assert response.json()["data"] == [], "Session should not appear on UTC date when user.timezone=Brisbane"

    def test_zone_offset_takes_precedence_over_user_timezone_sleep(self, client: TestClient, db: Session) -> None:
        """When both are set, zone_offset wins over user.timezone for sleep bucketing."""
        user = UserFactory(timezone=BRISBANE_TZ)
        mapping = DataSourceFactory(user=user, source="garmin")

        EventRecordFactory(
            mapping=mapping,
            category="sleep",
            start_datetime=SLEEP_START_UTC,
            end_datetime=SLEEP_END_UTC,
            duration_seconds=int((SLEEP_END_UTC - SLEEP_START_UTC).total_seconds()),
            zone_offset="+00:00",  # explicitly UTC — overrides Brisbane user.timezone
        )

        api_key = ApiKeyFactory()
        # Should appear on UTC date 2026-05-03 since zone_offset=+00:00
        response = client.get(
            f"/api/v1/users/{user.id}/summaries/sleep",
            headers=api_key_headers(api_key.plain_key),
            params={
                "start_date": "2026-05-03T00:00:00Z",
                "end_date": "2026-05-04T00:00:00Z",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1, "zone_offset=+00:00 should anchor wake date to 2026-05-03 (UTC)"
        assert data["data"][0]["date"] == SLEEP_WAKE_UTC_DATE


class TestSleepBucketingUtcFallback:
    """Case C: zone_offset NULL, user.timezone NULL — UTC fallback (upstream parity)."""

    def test_wake_date_falls_back_to_utc_when_no_timezone(self, client: TestClient, db: Session) -> None:
        """Without any timezone information, wake date is the UTC date."""
        user = UserFactory(timezone=None)
        mapping = DataSourceFactory(user=user, source="garmin")

        EventRecordFactory(
            mapping=mapping,
            category="sleep",
            start_datetime=SLEEP_START_UTC,
            end_datetime=SLEEP_END_UTC,
            duration_seconds=int((SLEEP_END_UTC - SLEEP_START_UTC).total_seconds()),
            zone_offset=None,
        )

        api_key = ApiKeyFactory()
        response = client.get(
            f"/api/v1/users/{user.id}/summaries/sleep",
            headers=api_key_headers(api_key.plain_key),
            params={
                "start_date": "2026-05-03T00:00:00Z",
                "end_date": "2026-05-04T00:00:00Z",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["date"] == SLEEP_WAKE_UTC_DATE


# ---------------------------------------------------------------------------
# Cross-user isolation
# ---------------------------------------------------------------------------


class TestBucketingCrossUserIsolation:
    """Timezone settings on one user must not affect another user's bucketing."""

    def test_utc_user_unaffected_by_brisbane_neighbour(self, client: TestClient, db: Session) -> None:
        """A UTC user's activity data must still bucket by UTC date."""
        utc_user = UserFactory(timezone=None)
        bris_user = UserFactory(timezone=BRISBANE_TZ)  # noqa: F841 — created to populate DB

        utc_mapping = DataSourceFactory(user=utc_user, source="apple")
        steps_type = SeriesTypeDefinitionFactory.get_or_create_steps()

        # UTC user's sample on 2026-05-02 UTC
        DataPointSeriesFactory(
            mapping=utc_mapping,
            series_type=steps_type,
            value=Decimal("1000"),
            recorded_at=RUN_UTC_START,
            zone_offset=None,
        )

        api_key = ApiKeyFactory()
        response = client.get(
            f"/api/v1/users/{utc_user.id}/summaries/activity",
            headers=api_key_headers(api_key.plain_key),
            params={
                "start_date": "2026-05-02T00:00:00Z",
                "end_date": "2026-05-03T00:00:00Z",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["date"] == RUN_UTC_DATE, (
            "UTC user's data must bucket to UTC date, not leak Brisbane timezone"
        )

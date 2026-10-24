from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from app.database import DbSession
from app.schemas.enums import SeriesType, SourceSelection
from app.schemas.model_crud.activities import TimeSeriesQueryParams
from app.schemas.responses.sdk_overview import OverviewMetric, OverviewPoint, OverviewTile, SdkOverview
from app.services.summaries_service import summaries_service
from app.services.timeseries_service import timeseries_service
from app.utils.pagination import MAX_PAGE_SIZE

UNITS = {
    OverviewMetric.STEPS: "count",
    OverviewMetric.SLEEP_MINUTES: "min",
    OverviewMetric.RESTING_HEART_RATE: "bpm",
    OverviewMetric.ACTIVE_CALORIES: "kcal",
}
# Totals of a day are summed; levels are averaged.
CHARTED = (OverviewMetric.STEPS, OverviewMetric.SLEEP_MINUTES, OverviewMetric.RESTING_HEART_RATE)


class SdkOverviewService:
    """The Connect app's Home screen data, read from the instance rather than the phone:
    a user with only a cloud account (say Garmin) has nothing on the phone to show."""

    def get_overview(self, db: DbSession, user_id: UUID, today: date, days: int) -> SdkOverview:
        first = today - timedelta(days=days)
        start = datetime.combine(first, time.min, tzinfo=timezone.utc)
        end = datetime.combine(today + timedelta(days=1), time.min, tzinfo=timezone.utc)

        values: dict[OverviewMetric, dict[date, float]] = defaultdict(dict)
        for day, (steps, active) in summaries_service.get_daily_activity_sums(db, user_id, start, end).items():
            if steps is not None:
                values[OverviewMetric.STEPS][day] = steps
            if active is not None:
                values[OverviewMetric.ACTIVE_CALORIES][day] = active
        sleep = summaries_service.get_sleep_summaries(db, user_id, start, end, None, MAX_PAGE_SIZE).data
        for summary in sleep:
            # A zero-length night is a stub record, not a night without sleep.
            if summary.duration_minutes:
                values[OverviewMetric.SLEEP_MINUTES][summary.date] = float(summary.duration_minutes)
        values[OverviewMetric.RESTING_HEART_RATE] = self._daily_resting_heart_rate(db, user_id, start, end)

        tiles = [
            self._tile(metric, values[metric], today, first)
            for metric in OverviewMetric
            if any(first <= day <= today for day in values[metric])
        ]
        chart_days = [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]
        series = {
            metric: [OverviewPoint(date=day, value=values[metric].get(day)) for day in chart_days] for metric in CHARTED
        }
        return SdkOverview(today=today, days=days, tiles=tiles, series=series)

    @staticmethod
    def _tile(metric: OverviewMetric, by_day: dict[date, float], today: date, first: date) -> OverviewTile:
        earlier = [value for day, value in by_day.items() if first <= day < today]
        average = sum(earlier) / len(earlier) if earlier else None
        value = by_day.get(today)
        delta = round((value - average) / average * 100, 1) if value is not None and average else None
        return OverviewTile(
            metric=metric,
            unit=UNITS[metric],
            today=value,
            average=round(average, 1) if average is not None else None,
            delta_percent=delta,
        )

    @staticmethod
    def _daily_resting_heart_rate(db: DbSession, user_id: UUID, start: datetime, end: datetime) -> dict[date, float]:
        """Resting heart rate is reported about once a day; average the samples of each day."""
        params = TimeSeriesQueryParams(start_datetime=start, end_datetime=end, limit=MAX_PAGE_SIZE)
        samples = timeseries_service.get_timeseries(
            db, user_id, [SeriesType.resting_heart_rate], params, source_selection=SourceSelection.PER_RANGE
        ).data
        by_day: dict[date, list[float]] = defaultdict(list)
        for sample in samples:
            by_day[sample.timestamp.date()].append(float(sample.value))
        return {day: round(sum(found) / len(found), 1) for day, found in by_day.items()}


sdk_overview_service = SdkOverviewService()

from collections.abc import Iterable
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from logging import getLogger
from typing import LiteralString, NamedTuple, overload
from typing import cast as typing_cast
from uuid import UUID

from psycopg import Connection as PGConnection
from psycopg.errors import UniqueViolation
from sqlalchemy import (
    Column,
    ColumnElement,
    Date,
    Integer,
    Interval,
    MetaData,
    String,
    Table,
    asc,
    case,
    cast,
    column,
    func,
    literal,
    literal_column,
    select,
    text,
    true,
    tuple_,
    values,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.exc import IntegrityError as SQLAIntegrityError
from sqlalchemy.orm import Query
from sqlalchemy.schema import CreateTable

from app.database import DbSession
from app.integrations.rollup_queue import mark_dirty_days
from app.models import (
    DataPointSeriesArchive,
    DataSource,
    DeviceTypePriority,
    EventRecord,
    EventRecordAggregate,
    ProviderPriority,
    SeriesAggregate,
    SeriesSample,
)
from app.models.series_type_definition import SeriesTypeDefinition
from app.repositories.aggregate_repository import AggregateRepository
from app.repositories.data_source_repository import DATA_SOURCE_FIELDS, DataSourceIdentity, DataSourceRepository
from app.repositories.data_type_coverage_repository import data_type_coverage_repository
from app.repositories.local_day import OFFSET_REACH
from app.repositories.repositories import (
    CrudRepository,
    source_filter_conditions,
    timeline_key_column,
    utc_bucket_start,
)
from app.repositories.series_aggregate_repository import LOCAL_DAY
from app.schemas.data_type_coverage import CoverageSpan
from app.schemas.enums import (
    BUCKET_SIZES,
    AggregationMethod,
    ComputedBy,
    PeriodKind,
    ProviderName,
    Resolution,
    SeriesType,
    TimelineBucket,
    TimelineGroupBy,
    get_series_type_from_id,
    get_series_type_id,
)
from app.schemas.enums.aggregation_method import get_aggregation_method
from app.schemas.enums.data_granularity import PERIOD_RESOLUTIONS
from app.schemas.model_crud.activities import (
    TimeSeriesQueryParams,
    TimeSeriesSampleCreate,
    TimeSeriesSampleUpdate,
)
from app.schemas.responses.activity import (
    ActiveMinutesResult,
    IntensityMinutesResult,
)
from app.schemas.sync_status import DataTypeKind
from app.utils.dates import as_utc, local_date
from app.utils.exceptions import handle_exceptions
from app.utils.pagination import decode_bucket_cursor, decode_cursor

logger = getLogger(__name__)


class TypeCounts(NamedTuple):
    """One series type's share of a bulk upsert."""

    inserted: int
    updated: int
    covered_start: datetime
    covered_end: datetime

    def merged_with(self, other: "TypeCounts") -> "TypeCounts":
        return TypeCounts(
            self.inserted + other.inserted,
            self.updated + other.updated,
            min(self.covered_start, other.covered_start),
            max(self.covered_end, other.covered_end),
        )


class _StagedSpan(NamedTuple):
    """The rows staged for one data source and series type: how many, and the span they cover."""

    staged: int
    start: datetime
    end: datetime


def _spans_by_source_and_type(
    rows: Iterable["DataPointSeriesRepository._StagingRow"],
) -> dict[tuple[UUID, int], _StagedSpan]:
    """One pass over the rows already in memory, so neither the counts nor coverage cost a query."""
    # Updated in place: a sample batch runs to millions of rows, and few keys.
    spans: dict[tuple[UUID, int], list] = {}
    for row in rows:
        at = row.recorded_at
        span = spans.get((row.data_source_id, row.series_type_definition_id))
        if span is None:
            spans[(row.data_source_id, row.series_type_definition_id)] = [1, at, at]
            continue
        span[0] += 1
        if at < span[1]:
            span[1] = at
        elif at > span[2]:
            span[2] = at
    return {key: _StagedSpan(*span) for key, span in spans.items()}


class WriteCounts(int):
    """Result of a bulk upsert: total rows written, split into new vs updated.

    Behaves as ``inserted + updated`` so existing int-based callers (sums,
    ``records_saved`` logging, ``dict[str, int]`` results) keep working
    unchanged, while callers that care about the difference can read
    ``.inserted`` (rows that did not exist) and ``.updated`` (rows refreshed
    in place via ON CONFLICT). Distinguishing the two is what stops a pure
    upsert-in-place from looking like newly arrived data.

    covered_start/covered_end are the oldest and newest ``recorded_at`` actually
    written. This is the span of the data itself, which is not the window that was
    requested: asking for 90 days and getting two weight readings covers two days.

    The totals are stored rather than summed from by_type: some write paths report a
    split without a per-type breakdown.
    """

    inserted: int
    updated: int
    # Keyed by canonical SeriesType slug, so run tracking can report per type rather
    # than per provider fetch task.
    by_type: dict[str, TypeCounts]

    def __new__(cls, inserted: int, updated: int, by_type: dict[str, TypeCounts] | None = None) -> "WriteCounts":
        obj = super().__new__(cls, inserted + updated)
        obj.inserted = inserted
        obj.updated = updated
        obj.by_type = by_type or {}
        return obj

    @property
    def covered_start(self) -> datetime | None:
        return min((counts.covered_start for counts in self.by_type.values()), default=None)

    @property
    def covered_end(self) -> datetime | None:
        return max((counts.covered_end for counts in self.by_type.values()), default=None)

    # Overloads are for the type checker: they tell it which addition keeps the split.
    @overload
    def __add__(self, other: "WriteCounts") -> "WriteCounts": ...

    @overload
    def __add__(self, other: int) -> int: ...

    def __add__(self, other: int) -> int:
        """Keep the split and widen the covered span when accumulating counts.

        A plain int has no split to keep, so adding one yields a plain int.
        """
        if not isinstance(other, WriteCounts):
            return int(self) + other
        by_type = dict(self.by_type)
        for series_type, counts in other.by_type.items():
            existing = by_type.get(series_type)
            by_type[series_type] = counts if existing is None else existing.merged_with(counts)
        return WriteCounts(self.inserted + other.inserted, self.updated + other.updated, by_type)

    def __radd__(self, other: int) -> int:
        # Makes sum() of WriteCounts work: the 0 start value passes the split through.
        if other == 0:
            return self
        return other + int(self)

    def __repr__(self) -> str:
        return f"WriteCounts(inserted={self.inserted}, updated={self.updated})"


# Sources whose provider or device type is not ranked sort last, in id order.
_UNRANKED = 1_000_000
SERIES_TYPE_IDS: tuple[int, ...] = tuple(get_series_type_id(t) for t in SeriesType)
_AGGREGATE_FUNCS = {
    AggregationMethod.AVG: func.avg,
    AggregationMethod.SUM: func.sum,
    AggregationMethod.MAX: func.max,
}
# Series type ids per non-default aggregation, resolved once: the mapping is static and the
# lookup would otherwise run per request. AVG is the else branch, so it needs no entry.
_TYPE_IDS_BY_METHOD: dict[AggregationMethod, frozenset[int]] = {
    method: frozenset(get_series_type_id(t) for t in SeriesType if get_aggregation_method(t) is method)
    for method in _AGGREGATE_FUNCS
    if method is not AggregationMethod.AVG
}


# Rows per avg HR query; 5 bind parameters each keeps a query far below PostgreSQL's 65535
_MAX_WINDOW_ROWS = 2000


class WorkoutWindow(NamedTuple):
    """A workout's time window, its own data source and the sources to fall back on for samples."""

    record_id: UUID
    data_source_id: UUID
    start_time: datetime
    end_time: datetime
    fallback_source_ids: tuple[UUID, ...] = ()


class AggregatedSample(NamedTuple):
    """One resolution bucket for a single (data source, series type) pair."""

    bucket: datetime
    series_type_definition_id: int
    value: Decimal
    zone_offset: str | None
    is_daily_total: bool
    data_source: DataSource


class DataPointSeriesRepository(
    CrudRepository[SeriesSample, TimeSeriesSampleCreate, TimeSeriesSampleUpdate],
):
    """Repository for unified device data point series."""

    def __init__(self, model: type[SeriesSample]):
        super().__init__(model)
        self.data_source_repo = DataSourceRepository()
        self.series_aggregate_repo = AggregateRepository(SeriesAggregate)
        self.event_aggregate_repo = AggregateRepository(EventRecordAggregate)

    @handle_exceptions
    def create(self, db_session: DbSession, creator: TimeSeriesSampleCreate) -> SeriesSample:
        """Create a data point sample, or return existing if duplicate.

        Handles duplicate records gracefully by catching IntegrityError and
        returning the existing record instead.
        """
        data_source = self.data_source_repo.ensure_for_creator(db_session, creator)

        creation_data = creator.model_dump(
            exclude={*DATA_SOURCE_FIELDS, "series_type", "data_source_id", "period", "session"}
        )

        # Set the proper values
        creation_data["data_source_id"] = data_source.id
        creation_data["series_type_definition_id"] = get_series_type_id(creator.series_type)

        creation = self.model(**creation_data)
        db_session.add(creation)
        mark_dirty_days(db_session, [(data_source.id, local_date(creator.recorded_at, creator.zone_offset))])
        created = self.try_commit(db_session, creation)
        # After the commit: a duplicate rolls the sample back and returns the stored one, and its day or
        # session value must still land.
        if creator.period is not None or creator.session is not None:
            self._mirror_aggregates(db_session, [creator], {DataSourceIdentity.of(creator): data_source.id})
            db_session.commit()
        return created

    @handle_exceptions
    def bulk_create(self, db_session: DbSession, creators: list[TimeSeriesSampleCreate]) -> WriteCounts:
        """Bulk create data point samples.

        Optimized for performance:
        - Resolves data sources efficiently (batch fetch + batch insert missing)
        - Inserts data points in a single batch

        Returns the number of rows actually written, split into inserted (new)
        vs updated (refreshed in place via ON CONFLICT).
        """
        if not creators:
            return WriteCounts(0, 0)

        # 1. Resolve all data sources in batch
        identity_to_source_id = self.data_source_repo.resolve_creators(db_session, creators)

        # 2. Build and execute data point batch insert
        rows, owners = self._staging_rows(creators, identity_to_source_id)
        if not rows:
            return WriteCounts(0, 0)
        spans = _spans_by_source_and_type(rows)
        counts = self._insert_data_points(db_session, rows, spans)
        self._mirror_aggregates(db_session, self._with_live_sessions(db_session, creators), identity_to_source_id)
        mark_dirty_days(
            db_session, {(row.data_source_id, local_date(row.recorded_at, row.zone_offset)) for row in rows}
        )

        # 3. Widen what we hold per type, under the same provider the sources resolved to
        data_type_coverage_repository.record(
            db_session,
            (
                CoverageSpan(
                    user_id=owners[source_id][0],
                    provider=owners[source_id][1],
                    data_type=get_series_type_from_id(type_id).value,
                    kind=DataTypeKind.SERIES,
                    start=span.start,
                    end=span.end,
                )
                for (source_id, type_id), span in spans.items()
            ),
        )
        return counts

    @staticmethod
    def _with_live_sessions(
        db_session: DbSession, creators: list[TimeSeriesSampleCreate]
    ) -> list[TimeSeriesSampleCreate]:
        """Session values pointing at a record that no longer exists (a sleep merged away meanwhile) are kept as
        samples only: a foreign-key error on one of them would lose the whole batch."""
        record_ids = {c.session.record_id for c in creators if c.session is not None}
        if not record_ids:
            return creators
        live = {record_id for (record_id,) in db_session.query(EventRecord.id).filter(EventRecord.id.in_(record_ids))}
        if gone := record_ids - live:
            logger.warning("Session values of %d samples point at deleted records; kept as samples only", len(gone))
            return [
                c.model_copy(update={"session": None}) if c.session is not None and c.session.record_id in gone else c
                for c in creators
            ]
        return creators

    def _mirror_aggregates(
        self,
        db_session: DbSession,
        creators: list[TimeSeriesSampleCreate],
        source_map: dict[DataSourceIdentity, UUID],
    ) -> None:
        """Mirror provider values that name their calendar period or event into the aggregate tables."""
        period_rows, session_rows = [], []
        for creator in creators:
            if creator.period is None and creator.session is None:
                continue
            type_id = get_series_type_id(creator.series_type)
            canonical = get_aggregation_method(creator.series_type).value
            if creator.period is not None and (source_id := source_map.get(DataSourceIdentity.of(creator))):
                period_rows.append(
                    {
                        "data_source_id": source_id,
                        "series_type_definition_id": type_id,
                        "period_kind": creator.period.kind,
                        "period_start": creator.period.start,
                        "period_end": creator.period.end,
                        "zone_offset": creator.period.zone_offset,
                        "computed_by": ComputedBy.PROVIDER,
                        canonical: creator.value,
                        "count": 1,
                    }
                )
            if creator.session is not None:
                session_rows.append(
                    {
                        "record_id": creator.session.record_id,
                        "series_type_definition_id": type_id,
                        "computed_by": ComputedBy.PROVIDER,
                        creator.session.stat or canonical: creator.value,
                        "count": 1,
                    }
                )
        if period_rows:
            self.series_aggregate_repo.upsert(db_session, period_rows)
        if session_rows:
            self.event_aggregate_repo.upsert(db_session, session_rows)

    class _StagingRow(NamedTuple):
        """One row as loaded into series_sample_staging via COPY, in column order."""

        id: UUID
        external_id: str | None
        data_source_id: UUID
        recorded_at: datetime
        zone_offset: str | None
        window_seconds: int | None
        value: Decimal | float | int
        series_type_definition_id: int
        is_daily_total: bool | None

    # Single source of truth for the COPY/INSERT column list, derived from _StagingRow's
    # own field names above so the SQL text and the row shape can't drift apart.
    _COPY_COLUMNS_SQL = typing_cast(LiteralString, ", ".join(_StagingRow._fields))  # ty:ignore[redundant-cast]

    def _staging_rows(
        self, creators: list[TimeSeriesSampleCreate], source_map: dict[DataSourceIdentity, UUID]
    ) -> tuple[list["DataPointSeriesRepository._StagingRow"], dict[UUID, tuple[UUID, str]]]:
        """The rows to merge, one per key, and the user and provider each data source belongs to."""
        rows: list[DataPointSeriesRepository._StagingRow] = []
        owners: dict[UUID, tuple[UUID, str]] = {}
        for creator in creators:
            source_id = source_map.get(DataSourceIdentity.of(creator))
            if not source_id:
                # Should not happen if resolve logic is correct, but safe skip.
                continue
            if source_id not in owners:
                owners[source_id] = (creator.user_id, self.data_source_repo.provider_of(creator).value)
            rows.append(
                self._StagingRow(
                    id=creator.id,
                    external_id=creator.external_id,
                    data_source_id=source_id,
                    recorded_at=creator.recorded_at,
                    zone_offset=creator.zone_offset,
                    window_seconds=creator.window_seconds,
                    value=creator.value,
                    series_type_definition_id=get_series_type_id(creator.series_type),
                    is_daily_total=creator.is_daily_total,
                )
            )

        # Dedup within the batch: PostgreSQL cannot upsert the same row twice in one
        # statement. Keep the last value for each conflicting key.
        deduped: dict[tuple[UUID, int, datetime], DataPointSeriesRepository._StagingRow] = {}
        for row in rows:
            deduped[(row.data_source_id, row.series_type_definition_id, row.recorded_at)] = row
        return list(deduped.values()), owners

    def _insert_data_points(
        self,
        db_session: DbSession,
        rows: list["DataPointSeriesRepository._StagingRow"],
        spans: dict[tuple[UUID, int], "_StagedSpan"],
    ) -> WriteCounts:
        """Batch insert data points via COPY into a staging table + one merge statement.

        Returns the split of rows actually written (inserted vs updated). The split is
        derived from ``RETURNING (xmax = 0)`` on the merge statement.
        """

        raw_conn: PGConnection | None = db_session.connection().connection.driver_connection
        assert raw_conn is not None, "no DBAPI connection on an active Session"
        with raw_conn.cursor() as cursor:
            # Create the temporary staging table for bulk-importing data points.
            model_columns = SeriesSample.__table__.c
            staging_table = Table(
                "series_sample_staging",
                MetaData(),
                *(Column(name, model_columns[name].type) for name in self._StagingRow._fields),
                prefixes=["TEMPORARY"],
                postgresql_on_commit="DELETE ROWS",
            )
            staging_ddl = str(CreateTable(staging_table, if_not_exists=True).compile(dialect=postgresql.dialect()))
            cursor.execute(typing_cast(LiteralString, staging_ddl))
            cursor.execute("TRUNCATE series_sample_staging")
            # Raw psycopg connection sharing this Session's transaction - COPY has no
            # SQLAlchemy Core equivalent, and using a separate connection would commit
            # outside this transaction.
            with cursor.copy(f"COPY series_sample_staging ({self._COPY_COLUMNS_SQL}) FROM STDIN") as copy:
                for row in rows:
                    copy.write_row(row)

            cursor.execute(
                f"""
                    WITH merged AS (
                        INSERT INTO series_sample ({self._COPY_COLUMNS_SQL})
                        SELECT {self._COPY_COLUMNS_SQL} FROM series_sample_staging
                        ORDER BY data_source_id, series_type_definition_id, recorded_at
                        ON CONFLICT (data_source_id, series_type_definition_id, recorded_at)
                        DO UPDATE SET
                            external_id = excluded.external_id,
                            value = excluded.value,
                            zone_offset = excluded.zone_offset,
                            window_seconds = excluded.window_seconds,
                            is_daily_total = excluded.is_daily_total
                        WHERE series_sample.value IS DISTINCT FROM excluded.value
                           OR series_sample.external_id IS DISTINCT FROM excluded.external_id
                           OR series_sample.zone_offset IS DISTINCT FROM excluded.zone_offset
                           OR series_sample.window_seconds IS DISTINCT FROM excluded.window_seconds
                           OR series_sample.is_daily_total IS DISTINCT FROM excluded.is_daily_total
                        RETURNING (xmax = 0) AS was_insert, series_type_definition_id
                    )
                    SELECT series_type_definition_id, count(*) FILTER (WHERE was_insert) AS inserted
                    FROM merged
                    GROUP BY series_type_definition_id
                """
            )
            inserted_by_type_id = dict(cursor.fetchall())

        # Staged per type across its sources; updated is staged minus inserted, matching the
        # run-level split: a conflict whose values were unchanged never reaches RETURNING,
        # and still counts as written.
        staged_by_type: dict[int, TypeCounts] = {}
        for (_, type_id), span in spans.items():
            staged = TypeCounts(0, span.staged, span.start, span.end)
            known = staged_by_type.get(type_id)
            staged_by_type[type_id] = staged if known is None else known.merged_with(staged)
        by_type: dict[str, TypeCounts] = {}
        for type_id, staged in staged_by_type.items():
            inserted_for_type = inserted_by_type_id.get(type_id, 0)
            by_type[get_series_type_from_id(type_id).value] = staged._replace(
                inserted=inserted_for_type, updated=staged.updated - inserted_for_type
            )

        inserted = sum(inserted_by_type_id.values())
        return WriteCounts(inserted, len(rows) - inserted, by_type)

    def try_commit(self, db_session: DbSession, creation: SeriesSample) -> SeriesSample:
        try:
            db_session.commit()
            db_session.refresh(creation)
            return creation
        except SQLAIntegrityError as e:
            if isinstance(e.orig, UniqueViolation):
                db_session.rollback()

                # Query for existing record using the unique constraint fields
                existing = (
                    db_session.query(self.model)
                    .filter(
                        self.model.data_source_id == creation.data_source_id,
                        self.model.series_type_definition_id == creation.series_type_definition_id,
                        self.model.recorded_at == creation.recorded_at,
                    )
                    .first()
                )

                if existing:
                    return existing
            # Re-raise if not a duplicate or if existing record not found
            raise

    def get_samples(
        self,
        db_session: DbSession,
        params: TimeSeriesQueryParams,
        types: list[SeriesType],
        user_id: UUID,
        source_by_type: dict[int, UUID] | None = None,
    ) -> tuple[list[tuple[SeriesSample, DataSource]], int | None]:
        """Get data points with filtering and keyset pagination.

        Returns (samples, total_count). The count is a full aggregate over the largest table in
        the system, so it is taken on the first page only and is None on every page reached by
        cursor; the total cannot change under a keyset page, so the caller keeps the first value.
        """
        query = self._apply_sample_filters(
            db_session.query(self.model, DataSource)
            .join(
                DataSource,
                self.model.data_source_id == DataSource.id,
            )
            .filter(DataSource.user_id == user_id),
            params,
            types,
            params.start_datetime,
            params.end_datetime,
            source_by_type,
        )

        total_count = query.count() if params.cursor is None else None

        # Cursor pagination (keyset)
        if params.cursor:
            cursor_ts, cursor_id, direction = decode_cursor(params.cursor)

            if direction == "prev":
                # Backward pagination: get items BEFORE cursor
                query = query.filter(
                    tuple_(self.model.recorded_at, self.model.id) < (cursor_ts, cursor_id),
                )
                query = query.order_by(self.model.recorded_at.desc(), self.model.id.desc())
                # Limit + 1 to check for previous page
                limit = params.limit or 50
                results = query.limit(limit + 1).all()
                # Reverse to get correct order
                return list(reversed(results)), total_count
            # Forward pagination: get items AFTER cursor
            query = query.filter(
                tuple_(self.model.recorded_at, self.model.id) > (cursor_ts, cursor_id),
            )

        # Normal ascending order for forward pagination
        query = query.order_by(asc(self.model.recorded_at), asc(self.model.id))

        # Limit + 1 to check for next page
        limit = params.limit or 50
        return query.limit(limit + 1).all(), total_count

    def get_aggregated_samples(
        self,
        db_session: DbSession,
        params: TimeSeriesQueryParams,
        types: list[SeriesType],
        user_id: UUID,
        source_by_type: dict[int, UUID] | None = None,
    ) -> tuple[list[AggregatedSample], bool]:
        """Bucket samples into fixed-width windows, one row per (bucket, source, series type).

        Scans at most ``limit + 1`` buckets rather than the requested range: LIMIT cannot be
        pushed through a GROUP BY, so without the cap a month of 1 Hz data sorts every matching
        row (~50 MB to disk) just to return one page. Returns the rows and whether more follow.
        """
        bucket_size = BUCKET_SIZES[params.resolution]
        limit = params.limit or 50

        start, end, backward = self._resolve_window(params, bucket_size)
        if start is not None and end is not None and start >= end:
            return [], False
        requested_start, requested_end = start, end

        if not backward:
            start = (
                self._first_sample_at_or_after(db_session, params, types, user_id, start, end, source_by_type) or start
            )
            if start is None:
                return [], False

        span = bucket_size * (limit + 1)
        if backward and end is not None:
            start = end - span if start is None else max(start, end - span)
        elif not backward and start is not None:
            end = start + span if end is None else min(end, start + span)

        bucket = func.date_bin(
            cast(literal(f"{int(bucket_size.total_seconds())} seconds"), Interval),
            self.model.recorded_at,
            literal(datetime(1970, 1, 1, tzinfo=timezone.utc)),
        ).label("bucket")

        # DataSource is joined to filter by owner, never selected: its columns would ride
        # through the pre-aggregation sort and double what spills to disk.
        query = self._apply_sample_filters(
            db_session.query(
                bucket,
                self.model.series_type_definition_id.label("series_type_definition_id"),
                self.model.data_source_id.label("data_source_id"),
                self._aggregated_value(types).label("value"),
                func.min(self.model.zone_offset).label("zone_offset"),
            )
            .join(DataSource, self.model.data_source_id == DataSource.id)
            .filter(DataSource.user_id == user_id)
            # A day's own total would land inside one bucket and double-count the day.
            .filter(self.model.is_daily_total.isnot(True))
            .group_by(bucket, self.model.series_type_definition_id, self.model.data_source_id)
            .order_by(
                bucket.desc() if backward else bucket,
                self.model.data_source_id,
                self.model.series_type_definition_id,
            ),
            params,
            types,
            start,
            end,
            source_by_type,
        )

        rows = query.all()
        sources = self._sources_by_id(db_session, {r.data_source_id for r in rows})
        samples = [
            AggregatedSample(
                bucket=r.bucket,
                series_type_definition_id=r.series_type_definition_id,
                value=r.value,
                zone_offset=r.zone_offset,
                is_daily_total=False,
                data_source=sources[r.data_source_id],
            )
            for r in rows
        ]
        # A capped window is not a next page on its own: hand out a cursor only if the slice of
        # the requested range we skipped actually holds data.
        skipped = (requested_start, start) if backward else (end, requested_end)
        has_more = skipped[0] != skipped[1] and (
            self._first_sample_at_or_after(db_session, params, types, user_id, *skipped, source_by_type) is not None
        )
        return samples, has_more

    @staticmethod
    def _sources_by_id(db_session: DbSession, source_ids: set[UUID]) -> dict[UUID, DataSource]:
        if not source_ids:
            return {}
        return {s.id: s for s in db_session.query(DataSource).filter(DataSource.id.in_(source_ids))}

    def _apply_sample_filters(
        self,
        query: Query,
        params: TimeSeriesQueryParams,
        types: list[SeriesType],
        start: datetime | None,
        end: datetime | None,
        source_by_type: dict[int, UUID] | None = None,
    ) -> Query:
        """Filters shared by every sample read. Assumes DataSource is already joined."""
        if types:
            query = query.filter(self.model.series_type_definition_id.in_([get_series_type_id(t) for t in types]))
        query = query.filter(*source_filter_conditions(params, self.model.data_source_id))
        if start is not None:
            query = query.filter(self.model.recorded_at >= start)
        if end is not None:
            query = query.filter(self.model.recorded_at < end)
        if source_by_type is not None:
            query = query.filter(
                tuple_(self.model.series_type_definition_id, self.model.data_source_id).in_(
                    list(source_by_type.items())
                )
            )
        return query

    def winning_source_by_series_type(
        self,
        db_session: DbSession,
        params: TimeSeriesQueryParams,
        types: list[SeriesType],
        user_id: UUID,
        provider_order: dict,
        device_type_order: dict,
    ) -> dict[int, UUID]:
        """Best-ranked data source per series type, among those holding data in the window.

        Decided on source metadata plus one existence probe per (source, series type), so the
        cost tracks the number of devices a user owns rather than the number of samples. The
        winner is resolved per series type, so a watch with heart rate but no GPS keeps the
        heart rate and yields only the GPS series to the next source.
        """
        ranked = self._ranked_sources(db_session, params, user_id, provider_order, device_type_order)
        type_ids = [get_series_type_id(t) for t in types] if types else SERIES_TYPE_IDS
        if not ranked or not type_ids:
            return {}

        start, end = params.start_datetime, params.end_datetime
        candidates = values(
            column("type_id", Integer),
            column("source_id", PGUUID(as_uuid=True)),
            name="candidates",
        ).data([(type_id, source.id) for type_id in type_ids for source in ranked])
        if params.resolution in PERIOD_RESOLUTIONS:
            # Day, week and month reads come from the day rows, so that is where a source must hold
            # something: retention may have deleted its samples while its day rows stay, and a source
            # with only a provider day value (a Whoop cycle's steps) has exactly what these return.
            source, series, at = (
                SeriesAggregate.data_source_id,
                SeriesAggregate.series_type_definition_id,
                SeriesAggregate.period_start,
            )
            # The same local days the read then returns: the UTC reach alone would crown a source on a row
            # just past the range, and the read would come back empty.
            available = [SeriesAggregate.period_kind == PeriodKind.DAY]
            if start is not None:
                available.extend([at >= start - OFFSET_REACH, start.date() <= LOCAL_DAY])
            if end is not None:
                available.extend([at < end + OFFSET_REACH, (end - timedelta(microseconds=1)).date() >= LOCAL_DAY])
        else:
            source, series, at = self.model.data_source_id, self.model.series_type_definition_id, self.model.recorded_at
            available = [at >= start] if start is not None else []
            if end is not None:
                available.append(at < end)
            if params.resolution is not Resolution.RAW:
                # Bucketed reads drop daily totals, so a source holding only those has nothing to
                # offer here and must not outrank one with real intraday samples.
                available.append(self.model.is_daily_total.isnot(True))
        probe = (
            select(literal_column("1"))
            .where(source == candidates.c.source_id, series == candidates.c.type_id, *available)
            # Ordering on the index's trailing column lets the planner stop at the first match
            # instead of costing this as a full scan once a non-indexed filter is present.
            .order_by(at)
            .limit(1)
            .lateral("probe")
        )
        populated = db_session.execute(
            select(candidates.c.type_id, candidates.c.source_id).select_from(candidates.join(probe, true()))
        ).all()

        rank_of = {source.id: position for position, source in enumerate(ranked)}
        winners: dict[int, UUID] = {}
        for type_id, source_id in populated:
            if type_id not in winners or rank_of[source_id] < rank_of[winners[type_id]]:
                winners[type_id] = source_id
        return winners

    def count_sources(self, db_session: DbSession, user_id: UUID, params: TimeSeriesQueryParams) -> int:
        """How many of the caller's data sources a read may touch, honouring its source filters."""
        return (
            db_session.query(func.count(DataSource.id))
            .filter(DataSource.user_id == user_id, *source_filter_conditions(params, DataSource.id))
            .scalar()
            or 0
        )

    def _ranked_sources(
        self,
        db_session: DbSession,
        params: TimeSeriesQueryParams,
        user_id: UUID,
        provider_order: dict,
        device_type_order: dict,
    ) -> list[DataSource]:
        """The caller's sources, best first. Honours the source filters, so priority picks a
        winner from what the request actually asked for rather than from everything owned."""
        query = db_session.query(DataSource).filter(
            DataSource.user_id == user_id,
            *source_filter_conditions(params, DataSource.id),
        )
        return sorted(
            query.all(),
            key=lambda s: (
                provider_order.get(s.provider, _UNRANKED),
                device_type_order.get(s.device_type, _UNRANKED),
                s.id,
            ),
        )

    def _first_sample_at_or_after(
        self,
        db_session: DbSession,
        params: TimeSeriesQueryParams,
        types: list[SeriesType],
        user_id: UUID,
        start: datetime | None,
        end: datetime | None,
        source_by_type: dict[int, UUID] | None = None,
    ) -> datetime | None:
        """Timestamp of the earliest matching sample in the range, or None if there is none."""
        return self._apply_sample_filters(
            db_session.query(func.min(self.model.recorded_at))
            .join(DataSource, self.model.data_source_id == DataSource.id)
            .filter(DataSource.user_id == user_id),
            params,
            types,
            start,
            end,
            source_by_type,
        ).scalar()

    def _resolve_window(
        self,
        params: TimeSeriesQueryParams,
        bucket_size: timedelta,
    ) -> tuple[datetime | None, datetime | None, bool]:
        """Move the requested range to the cursor position. Returns (start, end, backward)."""
        start = params.start_datetime
        end = params.end_datetime

        backward = False
        if params.cursor:
            cursor_ts, direction = decode_bucket_cursor(params.cursor)
            backward = direction == "prev"
            if backward:
                end = cursor_ts
            else:
                start = cursor_ts + bucket_size

        return as_utc(start), as_utc(end), backward

    def _aggregated_value(self, types: list[SeriesType]) -> ColumnElement:
        """Pick avg/sum/max per series type from the shared coverage map, defaulting to avg."""
        requested = {get_series_type_id(t) for t in types} if types else None
        branches = []
        for method, type_ids in _TYPE_IDS_BY_METHOD.items():
            ids = sorted(type_ids & requested) if requested is not None else sorted(type_ids)
            if ids:
                branches.append(
                    (self.model.series_type_definition_id.in_(ids), _AGGREGATE_FUNCS[method](self.model.value))
                )
        if not branches:
            return func.avg(self.model.value)
        return case(*branches, else_=func.avg(self.model.value))

    def get_total_count(self, db_session: DbSession) -> int:
        """Get total count of all data points."""
        return db_session.query(func.count(self.model.id)).scalar() or 0

    @staticmethod
    def _approximate_row_count(db_session: DbSession, table_name: str) -> int:
        """Approximate row count of ``table_name`` from planner statistics (``pg_class.reltuples``).

        Instant (metadata lookup, no table scan), unlike a full ``COUNT(*)``. The estimate is
        refreshed by (auto)VACUUM/ANALYZE and may lag by a few percent, so it is only suitable for a
        non-critical dashboard figure. Postgres reports reltuples = -1 for a never-ANALYZEd table;
        clamp to 0.
        """
        result = db_session.execute(
            text("SELECT reltuples::bigint FROM pg_class WHERE oid = to_regclass(:table)"),
            {"table": table_name},
        ).scalar()
        return max(int(result or 0), 0)

    def get_approximate_total_count(self, db_session: DbSession) -> int:
        """Approximate total row count of the (hot) data point table."""
        return self._approximate_row_count(db_session, self.model.__tablename__)

    def get_approximate_archived_count(self, db_session: DbSession) -> int:
        """Approximate row count of the archive table (archived data points)."""
        return self._approximate_row_count(db_session, DataPointSeriesArchive.__tablename__)

    def get_approximate_aggregate_count(self, db_session: DbSession) -> int:
        """Approximate number of day and session rows: what the samples are rolled up into."""
        return sum(
            self._approximate_row_count(db_session, table.__tablename__)
            for table in (SeriesAggregate, EventRecordAggregate)
        )

    def get_count_in_range(self, db_session: DbSession, start_datetime: datetime, end_datetime: datetime) -> int:
        """Get count of data points within a datetime range."""
        return (
            db_session.query(func.count(self.model.id))
            .filter(self.model.recorded_at >= start_datetime)
            .filter(self.model.recorded_at < end_datetime)
            .scalar()
            or 0
        )

    def get_daily_histogram(self, db_session: DbSession, start_datetime: datetime, end_datetime: datetime) -> list[int]:
        """Get daily histogram of data points for the given date range.

        Returns a list of counts, one per day, ordered chronologically.
        """

        daily_counts = (
            db_session.query(cast(self.model.recorded_at, Date).label("date"), func.count(self.model.id).label("count"))
            .filter(self.model.recorded_at >= start_datetime)
            .filter(self.model.recorded_at < end_datetime)
            .group_by(cast(self.model.recorded_at, Date))
            .order_by(cast(self.model.recorded_at, Date))
            .all()
        )

        # Convert to list of counts, filling in zeros for missing days
        if not daily_counts:
            return []

        return [count for _, count in daily_counts]

    def get_user_counts_by_provider_and_type(
        self,
        db_session: DbSession,
        user_id: UUID,
        start_datetime: datetime | None = None,
        end_datetime: datetime | None = None,
    ) -> list[tuple[str, str, int]]:
        """Get data point counts for a user grouped by provider and series type.

        When ``start_datetime`` and/or ``end_datetime`` are provided, only data points whose
        ``recorded_at`` falls in the half-open interval ``[start, end)`` are counted. When both
        are omitted, all-time counts are returned (unchanged behaviour).

        Returns list of (provider, series_type_code, count) tuples ordered by provider, then count descending.
        """
        query = (
            db_session.query(
                DataSource.provider,
                SeriesTypeDefinition.code,
                # count(*), not count(id): id is not in the (source, type, time) index,
                # so counting it read every row from the table instead of the index.
                func.count().label("count"),
            )
            .select_from(self.model)
            .join(DataSource, self.model.data_source_id == DataSource.id)
            .join(SeriesTypeDefinition, self.model.series_type_definition_id == SeriesTypeDefinition.id)
            .filter(DataSource.user_id == user_id)
        )
        if start_datetime is not None:
            query = query.filter(self.model.recorded_at >= start_datetime)
        if end_datetime is not None:
            query = query.filter(self.model.recorded_at < end_datetime)

        results = (
            query.group_by(DataSource.provider, SeriesTypeDefinition.code)
            .order_by(DataSource.provider, func.count().desc())
            .all()
        )
        return [(provider, code, count) for provider, code, count in results]

    def get_user_timeline_counts(
        self,
        db_session: DbSession,
        user_id: UUID,
        bucket: TimelineBucket,
        group_by: TimelineGroupBy,
        start_datetime: datetime | None = None,
        end_datetime: datetime | None = None,
        provider: ProviderName | None = None,
    ) -> list[tuple[str, date, int]]:
        """Data point counts for a user, bucketed by time and grouped by provider or series type.

        Returns (key, bucket_start, count) for non-empty buckets only.
        """
        bucket_start = utc_bucket_start(bucket, self.model.recorded_at)
        key_column = timeline_key_column(group_by)

        query = (
            db_session.query(key_column, bucket_start, func.count().label("count"))
            .select_from(self.model)
            .join(DataSource, self.model.data_source_id == DataSource.id)
        )
        if group_by is TimelineGroupBy.SERIES_TYPE:
            query = query.join(SeriesTypeDefinition, self.model.series_type_definition_id == SeriesTypeDefinition.id)
        query = query.filter(DataSource.user_id == user_id)
        if provider is not None:
            query = query.filter(DataSource.provider == provider)
        if start_datetime is not None:
            query = query.filter(self.model.recorded_at >= start_datetime)
        if end_datetime is not None:
            query = query.filter(self.model.recorded_at < end_datetime)

        results = query.group_by(key_column, bucket_start).order_by(key_column, bucket_start).all()
        return [(key, bucket_start_value, count) for key, bucket_start_value, count in results]

    def get_count_by_source(self, db_session: DbSession) -> list[tuple[str | None, int]]:
        """Get count of data points grouped by source.

        Returns list of (source, count) tuples ordered by count descending.
        """
        results = (
            db_session.query(DataSource.source, func.count(self.model.id).label("count"))
            .join(DataSource, self.model.data_source_id == DataSource.id)
            .group_by(DataSource.source)
            .order_by(func.count(self.model.id).desc())
            .all()
        )
        return [(source, count) for source, count in results]

    def get_avg_hr_for_workout_batch(
        self,
        db_session: DbSession,
        workouts: list[WorkoutWindow],
    ) -> dict[UUID, int]:
        """Batch-compute average HR from series data for multiple workout windows.

        One query per chunk of workouts, a VALUES CTE joined against series_sample with one
        index range scan per (workout, source). HR from the workout's own source wins; the fallback
        sources are used only when it has none in the window.

        Returns:
            Dict mapping record_id to rounded avg HR. Workouts with no HR data are omitted.
        """
        result: dict[UUID, int] = {}
        chunk: list[WorkoutWindow] = []
        rows = 0
        for workout in workouts:
            # A workout's sources stay in one chunk, so its fallback average covers all of them
            workout_rows = 1 + len(workout.fallback_source_ids)
            if chunk and rows + workout_rows > _MAX_WINDOW_ROWS:
                result |= self._avg_hr_for_windows(db_session, chunk)
                chunk, rows = [], 0
            chunk.append(workout)
            rows += workout_rows
        if chunk:
            result |= self._avg_hr_for_windows(db_session, chunk)
        return result

    def _avg_hr_for_windows(self, db_session: DbSession, workouts: list[WorkoutWindow]) -> dict[UUID, int]:
        # Windows are passed as literals: computed in SQL, the planner loses the time bounds on the index
        values_parts: list[str] = []
        params: dict[str, object] = {"hr_type_id": get_series_type_id(SeriesType.heart_rate)}
        for workout in workouts:
            sources = [(workout.data_source_id, True), *((source, False) for source in workout.fallback_source_ids)]
            for data_source_id, is_own in sources:
                i = len(values_parts)
                values_parts.append(f"""(
                    CAST(:record_id_{i} AS uuid),
                    CAST(:ds_id_{i} AS uuid),
                    CAST(:is_own_{i} AS boolean),
                    CAST(:start_{i} AS timestamptz),
                    CAST(:end_{i} AS timestamptz)
                )""")
                params[f"record_id_{i}"] = str(workout.record_id)
                params[f"ds_id_{i}"] = str(data_source_id)
                params[f"is_own_{i}"] = is_own
                params[f"start_{i}"] = workout.start_time
                params[f"end_{i}"] = workout.end_time

        sql = text(f"""
            WITH workout_windows(record_id, data_source_id, is_own, start_time, end_time) AS (
                VALUES {", ".join(values_parts)}
            )
            SELECT ww.record_id, ww.is_own, ROUND(AVG(dps.value))::int
            FROM workout_windows ww
            JOIN series_sample dps
                ON dps.data_source_id = ww.data_source_id
                AND dps.series_type_definition_id = :hr_type_id
                AND dps.recorded_at >= ww.start_time
                AND dps.recorded_at < ww.end_time
            GROUP BY ww.record_id, ww.is_own
        """)

        own_avg: dict[UUID, int] = {}
        fallback_avg: dict[UUID, int] = {}
        for record_id, is_own, avg in db_session.execute(sql, params).fetchall():
            (own_avg if is_own else fallback_avg)[UUID(str(record_id))] = int(avg)
        return fallback_avg | own_avg

    def _local_day_window(
        self, local_date: ColumnElement, start_date: datetime, end_date: datetime
    ) -> list[ColumnElement[bool]]:
        """Samples whose local date falls in [start, end).

        Bounded on `recorded_at` as well, a day wider each side to cover any offset:
        the local date is an expression no index can use, so without it a window
        scanned from its start to the newest sample.
        """
        return [
            self.model.recorded_at >= start_date - timedelta(days=1),
            self.model.recorded_at < end_date + timedelta(days=1),
            local_date >= cast(start_date, Date),
            local_date < cast(end_date, Date),
        ]

    def get_daily_active_minutes(
        self,
        db_session: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
        active_threshold: int = 30,
    ) -> list[ActiveMinutesResult]:
        """Get daily active/sedentary minutes from step data.

        Buckets step data by minute and counts:
        - active_minutes: minutes with steps >= threshold
        - tracked_minutes: total minutes with any step data
        - sedentary_minutes: tracked_minutes - active_minutes

        Args:
            active_threshold: Steps per minute to be considered "active" (default: 30)

        Returns list of dicts with keys:
        - activity_date, source, device_model
        - active_minutes, tracked_minutes, sedentary_minutes
        """
        steps_id = get_series_type_id(SeriesType.steps)

        local_date = cast(
            self.model.recorded_at + cast(func.coalesce(self.model.zone_offset, "+00:00"), Interval),
            Date,
        )

        # Create minute bucket expression using literal 'minute' text
        minute_trunc = func.date_trunc(literal_column("'minute'"), self.model.recorded_at)

        # Subquery: bucket step data by minute and sum steps per minute
        minute_bucket = (
            db_session.query(
                local_date.label("activity_date"),
                DataSource.source,
                DataSource.device_model,
                minute_trunc.label("minute_bucket"),
                func.sum(self.model.value).label("steps_in_minute"),
            )
            .join(DataSource, self.model.data_source_id == DataSource.id)
            .filter(
                DataSource.user_id == user_id,
                *self._local_day_window(local_date, start_date, end_date),
                self.model.series_type_definition_id == steps_id,
                self.model.is_daily_total.isnot(True),
            )
            .group_by(
                local_date,
                DataSource.source,
                DataSource.device_model,
                minute_trunc,
            )
            .subquery()
        )

        # Main query: aggregate minute buckets to get daily active/tracked counts
        results = (
            db_session.query(
                minute_bucket.c.activity_date,
                minute_bucket.c.source,
                minute_bucket.c.device_model,
                # Count minutes where steps >= threshold (active)
                func.sum(case((minute_bucket.c.steps_in_minute >= active_threshold, 1), else_=0)).label(
                    "active_minutes"
                ),
                # Count all tracked minutes
                func.count(minute_bucket.c.minute_bucket).label("tracked_minutes"),
            )
            .group_by(
                minute_bucket.c.activity_date,
                minute_bucket.c.source,
                minute_bucket.c.device_model,
            )
            .order_by(asc(minute_bucket.c.activity_date))
            .all()
        )

        aggregates: list[ActiveMinutesResult] = []
        for row in results:
            active = int(row.active_minutes) if row.active_minutes else 0
            tracked = int(row.tracked_minutes) if row.tracked_minutes else 0
            sedentary = tracked - active

            aggregates.append(
                {
                    "activity_date": row.activity_date,
                    "source": row.source,
                    "device_model": row.device_model,
                    "active_minutes": active,
                    "tracked_minutes": tracked,
                    "sedentary_minutes": sedentary,
                }
            )
        return aggregates

    def get_daily_intensity_minutes(
        self,
        db_session: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
        light_min: int,
        light_max: int,
        moderate_max: int,
        vigorous_max: int,
    ) -> list[IntensityMinutesResult]:
        """Get daily intensity minutes from heart rate data.

        Buckets HR data by minute and categorizes by intensity zone based on
        provided HR thresholds. Zone boundaries are calculated by the service layer.

        Args:
            light_min: Lower bound for light zone (inclusive)
            light_max: Upper bound for light zone (inclusive)
            moderate_max: Upper bound for moderate zone (inclusive, lower bound is light_max + 1)
            vigorous_max: Upper bound for vigorous zone (inclusive, lower bound is moderate_max + 1)

        Returns list of dicts with keys:
        - activity_date, source, device_model
        - light_minutes, moderate_minutes, vigorous_minutes
        """
        hr_id = get_series_type_id(SeriesType.heart_rate)

        local_date = cast(
            self.model.recorded_at + cast(func.coalesce(self.model.zone_offset, "+00:00"), Interval),
            Date,
        )

        # Create minute bucket expression
        minute_trunc = func.date_trunc(literal_column("'minute'"), self.model.recorded_at)

        # Subquery: bucket HR data by minute and get avg HR per minute
        minute_bucket = (
            db_session.query(
                local_date.label("activity_date"),
                DataSource.source,
                DataSource.device_model,
                minute_trunc.label("minute_bucket"),
                func.avg(self.model.value).label("avg_hr_in_minute"),
            )
            .join(DataSource, self.model.data_source_id == DataSource.id)
            .filter(
                DataSource.user_id == user_id,
                *self._local_day_window(local_date, start_date, end_date),
                self.model.series_type_definition_id == hr_id,
            )
            .group_by(
                local_date,
                DataSource.source,
                DataSource.device_model,
                minute_trunc,
            )
            .subquery()
        )

        # Main query: categorize minute buckets into intensity zones
        results = (
            db_session.query(
                minute_bucket.c.activity_date,
                minute_bucket.c.source,
                minute_bucket.c.device_model,
                # Light: 50-63% of max HR
                func.sum(
                    case(
                        (
                            (minute_bucket.c.avg_hr_in_minute >= light_min)
                            & (minute_bucket.c.avg_hr_in_minute <= light_max),
                            1,
                        ),
                        else_=0,
                    )
                ).label("light_minutes"),
                # Moderate: 64-76% of max HR
                func.sum(
                    case(
                        (
                            (minute_bucket.c.avg_hr_in_minute > light_max)
                            & (minute_bucket.c.avg_hr_in_minute <= moderate_max),
                            1,
                        ),
                        else_=0,
                    )
                ).label("moderate_minutes"),
                # Vigorous: 77-93% of max HR
                func.sum(
                    case(
                        (
                            (minute_bucket.c.avg_hr_in_minute > moderate_max)
                            & (minute_bucket.c.avg_hr_in_minute <= vigorous_max),
                            1,
                        ),
                        else_=0,
                    )
                ).label("vigorous_minutes"),
            )
            .group_by(
                minute_bucket.c.activity_date,
                minute_bucket.c.source,
                minute_bucket.c.device_model,
            )
            .order_by(asc(minute_bucket.c.activity_date))
            .all()
        )

        aggregates: list[IntensityMinutesResult] = []
        for row in results:
            aggregates.append(
                {
                    "activity_date": row.activity_date,
                    "source": row.source,
                    "device_model": row.device_model,
                    "light_minutes": int(row.light_minutes) if row.light_minutes else 0,
                    "moderate_minutes": int(row.moderate_minutes) if row.moderate_minutes else 0,
                    "vigorous_minutes": int(row.vigorous_minutes) if row.vigorous_minutes else 0,
                }
            )
        return aggregates

    def get_latest_values_for_types(
        self,
        db_session: DbSession,
        user_id: UUID,
        before_date: datetime,
        series_types: list[SeriesType],
    ) -> dict[SeriesType, tuple[float, datetime, str | None, str | None, str | None, str | None]]:
        """Get the most recent value for each series type before a given date.

        Used for slow-changing measurements like weight, height, body fat %.

        Args:
            before_date: Only consider measurements recorded before this datetime

        Returns:
            Dict mapping SeriesType to tuple of
            (value, recorded_at, provider, source, device_model, device_type)
        """
        if not series_types:
            raise ValueError("series_types cannot be empty")

        type_ids = [get_series_type_id(t) for t in series_types]

        # Subquery to get the max recorded_at for each series type
        latest_subq = (
            db_session.query(
                self.model.series_type_definition_id,
                func.max(self.model.recorded_at).label("max_recorded_at"),
            )
            .join(DataSource, self.model.data_source_id == DataSource.id)
            .filter(
                DataSource.user_id == user_id,
                self.model.recorded_at < before_date,
                self.model.series_type_definition_id.in_(type_ids),
            )
            .group_by(self.model.series_type_definition_id)
            .subquery()
        )

        # Main query to get the actual values at those timestamps
        # Use DISTINCT ON to handle multiple records with identical timestamps
        # Order by priorities to prefer higher priority sources
        results = (
            db_session.query(
                self.model.series_type_definition_id,
                self.model.value,
                self.model.recorded_at,
                DataSource.provider,
                DataSource.source,
                DataSource.device_model,
                DataSource.device_type,
            )
            .join(DataSource, self.model.data_source_id == DataSource.id)
            .outerjoin(ProviderPriority, DataSource.provider == ProviderPriority.provider)
            .outerjoin(
                DeviceTypePriority,
                DataSource.device_type == cast(DeviceTypePriority.device_type, String),
            )
            .join(
                latest_subq,
                (self.model.series_type_definition_id == latest_subq.c.series_type_definition_id)
                & (self.model.recorded_at == latest_subq.c.max_recorded_at),
            )
            .filter(DataSource.user_id == user_id)
            # DISTINCT ON (PostgreSQL) ensures exactly one result per series type
            # Order by priorities (lower number = higher priority), then id desc as tiebreaker
            .distinct(self.model.series_type_definition_id)
            .order_by(
                self.model.series_type_definition_id,
                ProviderPriority.priority.asc().nulls_last(),
                DeviceTypePriority.priority.asc().nulls_last(),
                self.model.id.desc(),
            )
            .all()
        )

        # Build result dict
        latest_values: dict[SeriesType, tuple[float, datetime, str | None, str | None, str | None, str | None]] = {}
        for type_id, value, recorded_at, provider, source, device_model, device_type in results:
            try:
                series_type = get_series_type_from_id(type_id)
                latest_values[series_type] = (float(value), recorded_at, provider, source, device_model, device_type)
            except KeyError:
                pass

        return latest_values

    def get_aggregates_for_period(
        self,
        db_session: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
        series_types: list[SeriesType],
    ) -> dict[SeriesType, dict]:
        """Get aggregate statistics for each series type within a time period.

        Used for high-frequency measurements that need aggregation like
        resting heart rate, HRV, blood pressure.

        Returns:
            Dict mapping SeriesType to dict with keys: avg, min, max, count
        """
        if not series_types:
            raise ValueError("series_types cannot be empty")

        type_ids = [get_series_type_id(t) for t in series_types]

        results = (
            db_session.query(
                self.model.series_type_definition_id,
                func.avg(self.model.value).label("avg_value"),
                func.min(self.model.value).label("min_value"),
                func.max(self.model.value).label("max_value"),
                func.count(self.model.id).label("count"),
            )
            .join(DataSource, self.model.data_source_id == DataSource.id)
            .filter(
                DataSource.user_id == user_id,
                self.model.recorded_at >= start_date,
                self.model.recorded_at < end_date,
                self.model.series_type_definition_id.in_(type_ids),
            )
            .group_by(self.model.series_type_definition_id)
            .all()
        )

        # Build result dict
        aggregates: dict[SeriesType, dict] = {}
        for type_id, avg_val, min_val, max_val, count in results:
            try:
                series_type = get_series_type_from_id(type_id)
                aggregates[series_type] = {
                    "avg": float(avg_val) if avg_val is not None else None,
                    "min": float(min_val) if min_val is not None else None,
                    "max": float(max_val) if max_val is not None else None,
                    "count": count,
                }
            except KeyError:
                pass

        return aggregates

    def get_latest_reading_within_window(
        self,
        db_session: DbSession,
        user_id: UUID,
        series_type: SeriesType,
        window_start: datetime,
        window_end: datetime,
    ) -> tuple[float, datetime, str, str | None] | None:
        """Get the most recent reading for a series type within a time window.

        Used for point-in-time metrics like body temperature that are only
        relevant if recently measured. Returns None if no reading exists
        within the specified window.

        Args:
            series_type: The type of measurement to retrieve
            window_start: Start of the valid time window
            window_end: End of the valid time window (typically now)

        Returns:
            Tuple of (value, recorded_at, provider_name, device_id) or None if no recent reading
        """
        type_id = get_series_type_id(series_type)

        result = (
            db_session.query(
                self.model.value,
                self.model.recorded_at,
                DataSource.source,
                DataSource.device_model,
            )
            .join(DataSource, self.model.data_source_id == DataSource.id)
            .outerjoin(ProviderPriority, DataSource.provider == ProviderPriority.provider)
            .outerjoin(
                DeviceTypePriority,
                DataSource.device_type == cast(DeviceTypePriority.device_type, String),
            )
            .filter(
                DataSource.user_id == user_id,
                self.model.series_type_definition_id == type_id,
                self.model.recorded_at >= window_start,
                self.model.recorded_at <= window_end,
            )
            .order_by(
                self.model.recorded_at.desc(),
                ProviderPriority.priority.asc().nulls_last(),
                DeviceTypePriority.priority.asc().nulls_last(),
            )
            .first()
        )

        if result is None:
            return None

        value, recorded_at, provider_name, device_id = result
        return (float(value), recorded_at, provider_name, device_id)

    def query_series(
        self,
        db_session: DbSession,
        user_id: UUID,
        type_id: int,
        start_dt: datetime,
        end_dt: datetime,
    ) -> list[tuple[datetime, float]]:
        """Query raw (recorded_at, value) pairs for a given series type and time window.

        Filters by user (via DataSource), series type, and half-open interval
        [start_dt, end_dt), ordered by recorded_at ascending.
        """
        results = (
            db_session.query(self.model.recorded_at, self.model.value)
            .join(DataSource, self.model.data_source_id == DataSource.id)
            .filter(
                DataSource.user_id == user_id,
                self.model.series_type_definition_id == type_id,
                self.model.recorded_at >= start_dt,
                self.model.recorded_at < end_dt,
            )
            .order_by(self.model.recorded_at, self.model.id)
            .all()
        )
        return [(row.recorded_at, float(row.value)) for row in results]

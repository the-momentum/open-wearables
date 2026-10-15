import contextlib
from collections import defaultdict
from collections.abc import Sequence
from typing import NamedTuple, cast
from uuid import UUID, uuid4

from sqlalchemy import CursorResult, and_, asc, delete, select, text
from sqlalchemy.dialects.postgresql import insert

from app.constants.devices_map import infer_device_type, is_host_model
from app.constants.sdk_providers import SDK_PROVIDERS
from app.database import DbSession
from app.models import DataSource, HealthScore, ProviderPriority
from app.repositories.provider_priority_repository import ProviderPriorityRepository
from app.repositories.repositories import CrudRepository
from app.schemas.enums import DeviceType, ProviderName
from app.schemas.model_crud.activities import EventRecordCreate, TimeSeriesSampleCreate
from app.schemas.model_crud.data_priority import DataSourceCreate, DataSourceUpdate

SourceCreator = EventRecordCreate | TimeSeriesSampleCreate

# Creator fields that describe its data source rather than the record itself
DATA_SOURCE_FIELDS = frozenset(
    {
        "user_id",
        "provider",
        "user_connection_id",
        "device_model",
        "software_version",
        "source",
        "device_type",
        "device_id",
        "source_app_id",
        "device_manufacturer",
    }
)


class DataSourceIdentity(NamedTuple):
    """Fields a data source is matched on; ingest passes ids only when they are stable for the device or app."""

    user_id: UUID
    device_model: str | None
    source: str | None
    device_id: str | None
    source_app_id: str | None

    @classmethod
    def of(cls, obj: SourceCreator | DataSource) -> "DataSourceIdentity":
        """Identity of a record creator or a stored row."""
        return cls(obj.user_id, obj.device_model, obj.source, obj.device_id, obj.source_app_id)

    def with_clean_ids(self) -> "DataSourceIdentity":
        """Blank or whitespace-only ids count as absent."""
        return self._replace(
            device_id=(self.device_id or "").strip() or None,
            source_app_id=(self.source_app_id or "").strip() or None,
        )


class SourceDetails(NamedTuple):
    """Non-identity fields a record carries about its data source."""

    software_version: str | None = None
    original_source_name: str | None = None
    reported_type: DeviceType | None = None
    device_manufacturer: str | None = None


_INSERT_FIELDS = (
    "id",
    "user_id",
    "provider",
    "user_connection_id",
    "device_model",
    "software_version",
    "source",
    "device_type",
    "original_source_name",
    "device_id",
    "source_app_id",
    "device_manufacturer",
)


def _version_key(version: str) -> tuple[int, ...] | None:
    parts = version.split(".")
    return tuple(int(part) for part in parts) if all(part.isdigit() for part in parts) else None


def _is_newer_version(candidate: str, current: str | None) -> bool:
    """A history sync replays old versions in any order, so only a higher one replaces the stored one."""
    if current is None:
        return True
    new, old = _version_key(candidate), _version_key(current)
    return new is not None and old is not None and new > old


class DataSourceRepository(
    CrudRepository[DataSource, DataSourceCreate, DataSourceUpdate],
):
    def __init__(self, model: type[DataSource] = DataSource):
        super().__init__(model)

    def _load(
        self, db_session: DbSession, provider: ProviderName, user_ids: set[UUID], fresh: bool = False
    ) -> list[DataSource]:
        """All of the users' rows for the provider; a user has a handful, so matching runs in memory."""
        query = db_session.query(self.model).filter(self.model.provider == provider, self.model.user_id.in_(user_ids))
        return (query.populate_existing() if fresh else query).all()

    @staticmethod
    def _lock_users(db_session: DbSession, provider: ProviderName, user_ids: set[UUID]) -> None:
        """Serialize source creation per user and provider until commit, so concurrent batches see each other's rows."""
        for user_id in sorted(user_ids):
            db_session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                {"key": f"data_source:{user_id}:{provider.value}"},
            )

    def _match(self, rows: list[DataSource], identity: DataSourceIdentity, stamp: bool = True) -> DataSource | None:
        """Existing row for the identity; with stamp=False, only rows it matches without re-keying them."""
        return (
            self._keyed_match(rows, identity)
            or self._find(rows, identity)
            or self._writer_match(rows, identity)
            or (self._stampable(rows, identity) if stamp else None)
        )

    @staticmethod
    def _find(rows: list[DataSource], identity: DataSourceIdentity) -> DataSource | None:
        """Match on the most stable identifier present: device id, then app id + model, then model + source."""
        user_id, device_model, source, device_id, source_app_id = identity
        for row in rows:
            if row.user_id != user_id:
                continue
            if device_id:
                matched = row.device_id == device_id
            elif source_app_id:
                matched = (
                    row.device_id is None
                    and row.source_app_id == source_app_id
                    and (row.device_model or "") == (device_model or "")
                )
            else:
                matched = (
                    row.device_id is None
                    and row.source_app_id is None
                    and (row.device_model or "") == (device_model or "")
                    and (row.source or "") == (source or "")
                )
            if matched:
                return row
        return None

    @staticmethod
    def _writer_match(rows: list[DataSource], identity: DataSourceIdentity) -> DataSource | None:
        """A writer's only row when the model is unknown on one side.

        Unknown means not sent, or an Apple host code on a third-party writer (the iOS SDK reports the
        relaying iPhone), so those rows converge once the producing device's model arrives.
        """
        user_id, device_model, _, device_id, source_app_id = identity
        if device_id or not source_app_id:
            return None
        writer_rows = [
            r for r in rows if r.user_id == user_id and r.device_id is None and r.source_app_id == source_app_id
        ]
        if len(writer_rows) != 1:
            return None
        row = writer_rows[0]
        incoming_unknown = device_model is None or is_host_model(source_app_id, device_model)
        stored_unknown = row.device_model is None or is_host_model(row.source_app_id, row.device_model)
        return row if incoming_unknown or stored_unknown else None

    @staticmethod
    def _keyed_match(rows: list[DataSource], identity: DataSourceIdentity) -> DataSource | None:
        """The only keyed row with this model, for a record sent without ids (Samsung step counts).

        Checked before an exact match, so records keep joining it over a legacy row written before the ids arrived.
        """
        if identity.device_id or identity.source_app_id or not identity.device_model:
            return None
        keyed = [
            r
            for r in rows
            if r.user_id == identity.user_id
            and (r.device_id or r.source_app_id)
            and r.device_model == identity.device_model
        ]
        return keyed[0] if len(keyed) == 1 else None

    def _stampable(self, rows: list[DataSource], identity: DataSourceIdentity) -> DataSource | None:
        """Row written before its stable ids were known (app-id row for a new device id, else a legacy row)."""
        app_id_row = identity._replace(device_id=None)
        if identity.device_id and identity.source_app_id and (row := self._find(rows, app_id_row)):
            return row
        if identity.device_id or identity.source_app_id:
            return self._find(rows, identity._replace(device_id=None, source_app_id=None))
        return None

    def get_by_identity(
        self,
        db_session: DbSession,
        user_id: UUID,
        provider: ProviderName,
        device_model: str | None = None,
        source: str | None = None,
        device_id: str | None = None,
        source_app_id: str | None = None,
    ) -> DataSource | None:
        identity = DataSourceIdentity(user_id, device_model, source, device_id, source_app_id)
        return self._find(self._load(db_session, provider, {user_id}), identity)

    def ensure_data_source(
        self,
        db_session: DbSession,
        user_id: UUID,
        provider: ProviderName,
        user_connection_id: UUID | None = None,
        device_model: str | None = None,
        software_version: str | None = None,
        source: str | None = None,
        original_source_name: str | None = None,
        reported_type: DeviceType | None = None,
        device_id: str | None = None,
        source_app_id: str | None = None,
        device_manufacturer: str | None = None,
    ) -> DataSource:
        identity = DataSourceIdentity(user_id, device_model, source, device_id, source_app_id).with_clean_ids()
        details = SourceDetails(software_version, original_source_name, reported_type, device_manufacturer)
        return self._resolve_many(db_session, provider, [(identity, details)], user_connection_id)[identity]

    @staticmethod
    def provider_of(creator: SourceCreator) -> ProviderName:
        """The creator's explicit provider when valid, else the one inferred from its source."""
        if creator.provider:
            with contextlib.suppress(ValueError):
                return ProviderName(creator.provider)
        return ProviderName.from_source_string(creator.source)

    def ensure_for_creator(
        self, db_session: DbSession, creator: SourceCreator, original_source_name: str | None = None
    ) -> DataSource:
        return self.ensure_data_source(
            db_session,
            user_id=creator.user_id,
            provider=self.provider_of(creator),
            user_connection_id=creator.user_connection_id,
            device_model=creator.device_model,
            software_version=creator.software_version,
            source=creator.source,
            original_source_name=original_source_name,
            reported_type=creator.device_type,
            device_id=creator.device_id,
            source_app_id=creator.source_app_id,
            device_manufacturer=creator.device_manufacturer,
        )

    def resolve_creators(
        self, db_session: DbSession, creators: Sequence[SourceCreator]
    ) -> dict[DataSourceIdentity, UUID]:
        """Data source id per creator identity, resolved in one batch per provider."""
        by_provider: dict[ProviderName, list[SourceCreator]] = {}
        for creator in creators:
            by_provider.setdefault(self.provider_of(creator), []).append(creator)

        resolved: dict[DataSourceIdentity, UUID] = {}
        for provider, group in by_provider.items():
            sources: dict[DataSourceIdentity, SourceDetails] = {}
            for creator in group:
                identity = DataSourceIdentity.of(creator)
                known = sources.get(identity, SourceDetails())
                sources[identity] = SourceDetails(
                    software_version=known.software_version or creator.software_version or None,
                    reported_type=known.reported_type or creator.device_type or None,
                    device_manufacturer=known.device_manufacturer or creator.device_manufacturer or None,
                )
            resolved.update(self.batch_ensure_data_sources(db_session, provider, group[0].user_connection_id, sources))
        return resolved

    def _resolve_many(
        self,
        db_session: DbSession,
        provider: ProviderName,
        requests: list[tuple[DataSourceIdentity, SourceDetails]],
        user_connection_id: UUID | None,
    ) -> dict[DataSourceIdentity, DataSource]:
        """Resolve identities with one SELECT, one INSERT for the new rows and one re-read.

        New rows are matchable within the batch, so a writer's first records still converge into one row.
        A batch that creates rows takes a per-user lock first and re-reads, so concurrent batches converge too.
        """
        # Identities without ids last, so they can join keyed rows created in the same batch
        requests = sorted(requests, key=lambda r: r[0].device_id is None and r[0].source_app_id is None)
        user_ids = {identity.user_id for identity, _ in requests}
        known = self._load(db_session, provider, user_ids)
        # Inserting or stamping changes which rows a concurrent batch matches, so both run under the lock
        if any(self._match(known, identity, stamp=False) is None for identity, _ in requests):
            self._lock_users(db_session, provider, user_ids)
            known = self._load(db_session, provider, user_ids, fresh=True)
        pending: list[DataSource] = []
        resolved: dict[DataSourceIdentity, DataSource] = {}
        for identity, details in requests:
            existing = self._match(known, identity)
            if existing is None:
                existing = self._new_row(provider, identity, user_connection_id, details)
                known.append(existing)
                pending.append(existing)
            else:
                self._apply_updates(existing, provider, identity, user_connection_id, details)
            resolved[identity] = existing
        db_session.flush()
        if not pending:
            return resolved

        ProviderPriorityRepository(ProviderPriority).ensure_provider_exists(db_session, provider)
        values = [{field: getattr(row, field) for field in _INSERT_FIELDS} for row in pending]
        db_session.execute(insert(self.model).values(values).on_conflict_do_nothing())
        # Re-read so a row a concurrent sync inserted first is returned instead of the transient one
        stored = self._load(db_session, provider, {row.user_id for row in pending})
        pending_ids = {id(row) for row in pending}
        for identity, row in resolved.items():
            if id(row) in pending_ids:
                created = self._find(stored, DataSourceIdentity.of(row))
                assert created is not None
                resolved[identity] = created
        return resolved

    def _new_row(
        self,
        provider: ProviderName,
        identity: DataSourceIdentity,
        user_connection_id: UUID | None,
        details: SourceDetails,
    ) -> DataSource:
        user_id, device_model, source, device_id, source_app_id = identity
        device_type = infer_device_type(
            provider, device_model, details.original_source_name or source, details.reported_type
        )
        return self.model(
            id=uuid4(),
            user_id=user_id,
            provider=provider,
            user_connection_id=user_connection_id,
            device_model=device_model,
            software_version=details.software_version,
            source=source,
            device_type=device_type.value if device_type != DeviceType.UNKNOWN else None,
            original_source_name=details.original_source_name,
            device_id=device_id,
            source_app_id=source_app_id,
            device_manufacturer=details.device_manufacturer,
        )

    def _apply_updates(
        self,
        existing: DataSource,
        provider: ProviderName,
        identity: DataSourceIdentity,
        user_connection_id: UUID | None,
        details: SourceDetails,
    ) -> None:
        _, device_model, source, device_id, source_app_id = identity
        software_version, original_source_name, reported_type, device_manufacturer = details
        updates: dict[str, object] = {}
        if device_id and existing.device_id is None:
            updates["device_id"] = device_id
        if source_app_id and existing.source_app_id is None:
            updates["source_app_id"] = source_app_id
        # A writer's name (a renamed Apple Watch) is not part of an app-keyed row's identity, so it follows
        # the latest one. Not on device-id rows: Samsung names one device differently per data type. The
        # app id itself is only a fallback name and never replaces a real one.
        keyed_by_app = updates.get("source_app_id", existing.source_app_id) and not updates.get(
            "device_id", existing.device_id
        )
        if keyed_by_app and source and source != source_app_id and source != existing.source:
            updates["source"] = source
        # Keyed rows learn their model later (Polar sleep before the exercise, a writer's first model);
        # a relaying host's code is replaced by the producing device's model
        replaces_host = is_host_model(existing.source_app_id, existing.device_model) and not is_host_model(
            source_app_id, device_model
        )
        if device_model and (existing.device_model is None or replaces_host):
            updates["device_model"] = device_model
        model_replaced = "device_model" in updates
        effective_model = device_model if model_replaced else existing.device_model or device_model
        if user_connection_id and existing.user_connection_id is None:
            updates["user_connection_id"] = user_connection_id
        if software_version and _is_newer_version(software_version, existing.software_version):
            updates["software_version"] = software_version
        if device_manufacturer and existing.device_manufacturer is None:
            updates["device_manufacturer"] = device_manufacturer
        if original_source_name and existing.original_source_name is None:
            updates["original_source_name"] = original_source_name
        resolved = infer_device_type(
            provider,
            effective_model,
            original_source_name or existing.original_source_name or existing.source,
            reported_type,
        )
        # The stored type came from the host code, so it is replaced along with the model
        if model_replaced and replaces_host:
            device_type = resolved.value if resolved != DeviceType.UNKNOWN else None
        else:
            device_type = self.next_device_type(provider, existing.device_type, resolved)
        if device_type != existing.device_type:
            updates["device_type"] = device_type
        for field, value in updates.items():
            object.__setattr__(existing, field, value)

    @staticmethod
    def next_device_type(provider: ProviderName, current: str | None, resolved: DeviceType) -> str | None:
        """Cloud rows take the inferred type; SDK rows only upgrade from unset/"other"."""
        if provider.value not in SDK_PROVIDERS:
            return resolved.value if resolved != DeviceType.UNKNOWN else None
        if current in (None, DeviceType.OTHER) and resolved not in (DeviceType.UNKNOWN, current):
            return resolved.value
        return current

    def batch_ensure_data_sources(
        self,
        db_session: DbSession,
        provider: ProviderName,
        user_connection_id: UUID | None,
        sources: dict[DataSourceIdentity, SourceDetails],
    ) -> dict[DataSourceIdentity, UUID]:
        normalized = {identity: DataSourceIdentity(*identity).with_clean_ids() for identity in sources}
        requests = [(normalized[identity], details) for identity, details in sources.items()]
        if not requests:
            return {}
        resolved = self._resolve_many(db_session, provider, requests, user_connection_id)
        return {identity: resolved[key].id for identity, key in normalized.items()}

    def get_user_data_sources(
        self,
        db_session: DbSession,
        user_id: UUID,
    ) -> list[DataSource]:
        return (
            db_session.query(self.model)
            .filter(self.model.user_id == user_id)
            .order_by(asc(self.model.provider), asc(self.model.device_model))
            .all()
        )

    def get_writer_siblings(self, db_session: DbSession, data_source_ids: set[UUID]) -> dict[UUID, tuple[UUID, ...]]:
        """Other sources of the same user, provider and writer (app id, else source) for each given source.

        One writer can be split across sources by its device model (Health Connect apps reporting the model
        on some records only, Garmin dailies vs workouts), so its samples may sit next to its events.
        """
        if not data_source_ids:
            return {}
        owners = select(self.model.user_id).where(self.model.id.in_(data_source_ids))
        rows = db_session.query(self.model).filter(self.model.user_id.in_(owners)).all()
        writers = {row.id: (row.user_id, row.provider, row.source_app_id or row.source) for row in rows}
        by_writer: dict[tuple[UUID, str, str | None], list[UUID]] = defaultdict(list)
        for source_id, writer in writers.items():
            by_writer[writer].append(source_id)
        # A source with neither an app id nor a source name has no writer to share
        return {
            source_id: tuple(i for i in by_writer[writer] if i != source_id) if writer[2] else ()
            for source_id, writer in writers.items()
            if source_id in data_source_ids
        }

    def delete_user_provider_data(
        self,
        db_session: DbSession,
        user_id: UUID,
        provider: ProviderName,
    ) -> int:
        """Delete all of a user's data for a single provider.

        Deletes the user's health_score rows for the provider (some are not linked to
        a data_source), then the data_source rows. ON DELETE CASCADE on the data_source
        FK removes every dependent row - event_records, data_point_series (+ archive),
        event/sleep/workout/menstrual details and health_scores linked via data_source
        or event_record. Returns the number of data_source rows deleted.
        """
        db_session.execute(
            delete(HealthScore).where(
                and_(HealthScore.user_id == user_id, HealthScore.provider == provider),
            ),
        )
        result = cast(
            CursorResult,
            db_session.execute(
                delete(self.model).where(
                    and_(self.model.user_id == user_id, self.model.provider == provider),
                ),
            ),
        )
        db_session.commit()
        return result.rowcount

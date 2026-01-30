from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.database import DbSession
from app.models.device_type_priority import DeviceTypePriority
from app.schemas.device_type import DEFAULT_DEVICE_TYPE_PRIORITY, DeviceType


class DeviceTypePriorityRepository:
    def get_all_ordered(self, db: DbSession) -> list[DeviceTypePriority]:
        stmt = select(DeviceTypePriority).order_by(DeviceTypePriority.priority)
        return list(db.scalars(stmt).all())

    def get_by_device_type(self, db: DbSession, device_type: DeviceType) -> DeviceTypePriority | None:
        stmt = select(DeviceTypePriority).where(DeviceTypePriority.device_type == device_type)
        return db.scalar(stmt)

    def get_priority_order(self, db: DbSession) -> dict[DeviceType, int]:
        priorities = self.get_all_ordered(db)
        if not priorities:
            return DEFAULT_DEVICE_TYPE_PRIORITY
        return {p.device_type: p.priority for p in priorities}

    def upsert(self, db: DbSession, device_type: DeviceType, priority: int) -> DeviceTypePriority:
        now = datetime.now(UTC)
        stmt = (
            insert(DeviceTypePriority)
            .values(device_type=device_type, priority=priority, created_at=now, updated_at=now)
            .on_conflict_do_update(
                index_elements=["device_type"],
                set_={"priority": priority, "updated_at": now},
            )
            .returning(DeviceTypePriority)
        )
        result = db.execute(stmt)
        db.flush()
        return result.scalar_one()

    def bulk_update(
        self, db: DbSession, priorities: list[tuple[DeviceType, int]]
    ) -> list[DeviceTypePriority]:
        now = datetime.now(UTC)
        for device_type, priority in priorities:
            stmt = (
                insert(DeviceTypePriority)
                .values(device_type=device_type, priority=priority, created_at=now, updated_at=now)
                .on_conflict_do_update(
                    index_elements=["device_type"],
                    set_={"priority": priority, "updated_at": now},
                )
            )
            db.execute(stmt)
        db.flush()
        return self.get_all_ordered(db)

    def initialize_defaults(self, db: DbSession) -> list[DeviceTypePriority]:
        existing = self.get_all_ordered(db)
        if existing:
            return existing
        priorities = list(DEFAULT_DEVICE_TYPE_PRIORITY.items())
        return self.bulk_update(db, priorities)

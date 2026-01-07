from uuid import UUID

from sqlalchemy import select

from app.database import DbSession
from app.models.device import Device
from app.models.device_software import DeviceSoftware
from app.repositories.repositories import CrudRepository
from app.schemas.device import DeviceCreate, DeviceSoftwareCreate, DeviceSoftwareUpdate, DeviceUpdate


class DeviceSoftwareRepository(CrudRepository[DeviceSoftware, DeviceSoftwareCreate, DeviceSoftwareUpdate]):
    def __init__(self):
        super().__init__(DeviceSoftware)

    def ensure_software(self, db: DbSession, device_id: UUID, version: str) -> DeviceSoftware:
        """Get existing software version or create new one."""
        query = select(self.model).where(self.model.device_id == device_id, self.model.version == version)
        existing = db.execute(query).scalar_one_or_none()
        if existing:
            return existing

        return self.create(db, DeviceSoftwareCreate(device_id=device_id, version=version))


class DeviceRepository(CrudRepository[Device, DeviceCreate, DeviceUpdate]):
    def __init__(self):
        super().__init__(Device)
        self.software_repo = DeviceSoftwareRepository()

    def ensure_device(
        self,
        db: DbSession,
        provider_name: str,
        serial_number: str,
        name: str | None = None,
        sw_version: str | None = None,
    ) -> Device:
        """Get existing device or create new one. Also handles software version if provided."""
        query = select(self.model).where(
            self.model.provider_name == provider_name, self.model.serial_number == serial_number
        )
        existing = db.execute(query).scalar_one_or_none()

        if existing:
            device = existing
            # Update name if missing
            if name and not device.name or name and device.name == "Unknown Device" and name != "Unknown Device":
                device.name = name
                db.add(device)
                db.commit()
                db.refresh(device)
        else:
            device = self.create(
                db,
                DeviceCreate(provider_name=provider_name, serial_number=serial_number, name=name or "Unknown Device"),
            )

        if sw_version:
            self.software_repo.ensure_software(db, device.id, sw_version)

        return device

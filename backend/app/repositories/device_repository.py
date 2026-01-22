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

    def _create_without_commit(self, db: DbSession, creator: DeviceSoftwareCreate) -> DeviceSoftware:
        """Create device software without committing - flush only to get ID."""
        creation_data = creator.model_dump()
        creation = self.model(**creation_data)
        db.add(creation)
        db.flush()  # Flush to generate ID without committing
        return creation

    def ensure_software(self, db: DbSession, device_id: UUID, version: str) -> DeviceSoftware:
        """Get existing software version or create new one. Uses Redis cache to avoid N+1 queries."""
        # Lazy import to avoid circular dependency
        from app.services.device_cache_service import device_cache_service

        # Check Redis cache first
        cached_id = device_cache_service.get_device_software_id(device_id, version)
        if cached_id:
            # Reconstruct DeviceSoftware object (not attached to session)
            return DeviceSoftware(
                id=cached_id,
                device_id=device_id,
                version=version,
            )

        # Query database
        query = select(self.model).where(self.model.device_id == device_id, self.model.version == version)
        existing = db.execute(query).scalars().first()
        if existing:
            # Cache the ID
            device_cache_service.cache_device_software(existing.id, device_id, version)
            return existing

        # Create new software
        software = self._create_without_commit(db, DeviceSoftwareCreate(device_id=device_id, version=version))
        # Cache the ID
        device_cache_service.cache_device_software(software.id, device_id, version)
        return software


class DeviceRepository(CrudRepository[Device, DeviceCreate, DeviceUpdate]):
    def __init__(self):
        super().__init__(Device)
        self.software_repo = DeviceSoftwareRepository()

    def _create_without_commit(self, db: DbSession, creator: DeviceCreate) -> Device:
        """Create device without committing - flush only to get ID."""
        creation_data = creator.model_dump()
        creation = self.model(**creation_data)
        db.add(creation)
        db.flush()  # Flush to generate ID without committing
        return creation

    def ensure_device(
        self,
        db: DbSession,
        provider_name: str,
        serial_number: str,
        name: str | None = None,
        sw_version: str | None = None,
    ) -> Device:
        """Get existing device or create new one. Uses Redis cache to avoid N+1 queries."""
        # Lazy import to avoid circular dependency
        from app.services.device_cache_service import device_cache_service

        # Check Redis cache first
        cached_id = device_cache_service.get_device_id(provider_name, serial_number, name)
        if cached_id:
            # Reconstruct Device object (not attached to session)
            device = Device(
                id=cached_id,
                provider_name=provider_name,
                serial_number=serial_number,
                name=name,
            )
            # Still ensure software if needed
            if sw_version:
                self.software_repo.ensure_software(db, device.id, sw_version)
            return device

        # Query database
        query = select(self.model).where(
            self.model.provider_name == provider_name,
            self.model.serial_number == serial_number,
        )
        if name:
            query = query.where(self.model.name == name)

        existing = db.execute(query).scalars().first()

        if existing:
            device = existing
            # Update name if missing
            if name and not device.name or name and device.name == "Unknown Device" and name != "Unknown Device":
                device.name = name
                db.add(device)
                db.flush()  # Flush to get any changes without committing
        else:
            device = self._create_without_commit(
                db,
                DeviceCreate(
                    provider_name=provider_name,
                    serial_number=serial_number,
                    name=name or "Unknown Device",
                ),
            )

        # Cache the device ID
        device_cache_service.cache_device(device.id, provider_name, serial_number, name)

        if sw_version:
            self.software_repo.ensure_software(db, device.id, sw_version)

        return device

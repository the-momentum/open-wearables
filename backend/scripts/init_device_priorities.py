"""Initialize device type priority table with default values."""

from app.database import SessionLocal
from app.repositories.device_type_priority_repository import DeviceTypePriorityRepository


def init_device_priorities() -> None:
    """Initialize device type priorities with default values."""
    with SessionLocal() as db:
        device_repo = DeviceTypePriorityRepository()
        device_priorities = device_repo.initialize_defaults(db)
        db.commit()
        device_names = [str(p.device_type.value) for p in device_priorities]
        print(f"✓ Device type priorities initialized: {', '.join(device_names)}")


if __name__ == "__main__":
    init_device_priorities()

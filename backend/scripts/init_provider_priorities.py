"""Seed the provider priority table so every connectable provider is listed.

Rows are created lazily on the first data sync, which leaves the Settings >
Priorities list empty on a fresh deployment. This script fills in the gaps at
startup. Existing rows keep their priority; missing providers are appended
after them in the default order.
"""

from app.database import SessionLocal
from app.repositories.provider_priority_repository import ProviderPriorityRepository
from app.schemas.enums import DEFAULT_PROVIDER_PRIORITY


def init_provider_priorities() -> None:
    providers = sorted(DEFAULT_PROVIDER_PRIORITY, key=DEFAULT_PROVIDER_PRIORITY.__getitem__)

    with SessionLocal() as db:
        repo = ProviderPriorityRepository()
        created = repo.seed_missing_providers(db, providers)
        # Read before commit: the session expires attributes on commit and is closed below.
        names = [str(p.provider) for p in created]
        db.commit()

    if names:
        print(f"✓ Provider priorities seeded: {', '.join(names)}")
    else:
        print("✓ Provider priorities already complete")


if __name__ == "__main__":
    init_provider_priorities()

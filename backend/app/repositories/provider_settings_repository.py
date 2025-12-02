from sqlalchemy import select

from app.database import DbSession
from app.models import ProviderSetting


class ProviderSettingsRepository:
    """Repository for managing provider settings in database."""

    def get_all(self, db: DbSession) -> dict[str, bool]:
        """Get all provider settings as a map of provider_name -> is_enabled."""
        stmt = select(ProviderSetting)
        settings = db.execute(stmt).scalars().all()
        return {s.provider: s.is_enabled for s in settings}

    def upsert(self, db: DbSession, provider: str, is_enabled: bool) -> ProviderSetting:
        """Insert or update provider setting."""
        from sqlalchemy.dialects.postgresql import insert

        stmt = (
            insert(ProviderSetting)
            .values(provider=provider, is_enabled=is_enabled)
            .on_conflict_do_update(
                index_elements=["provider"],
                set_={"is_enabled": is_enabled},
            )
            .returning(ProviderSetting)
        )
        setting = db.execute(stmt).scalar_one()
        db.commit()
        return setting

    def ensure_all_providers_exist(self, db: DbSession, providers: list[str]) -> None:
        """Ensure all providers exist in database with default enabled=True."""
        from sqlalchemy.dialects.postgresql import insert

        # Get existing providers
        existing = self.get_all(db)

        # Insert missing providers with default enabled=True
        for provider in providers:
            if provider not in existing:
                stmt = insert(ProviderSetting).values(provider=provider, is_enabled=True)
                db.execute(stmt)

        db.commit()

    def bulk_update(self, db: DbSession, updates: dict[str, bool]) -> None:
        """Bulk update provider settings."""
        from sqlalchemy.dialects.postgresql import insert

        for provider, is_enabled in updates.items():
            stmt = (
                insert(ProviderSetting)
                .values(provider=provider, is_enabled=is_enabled)
                .on_conflict_do_update(
                    index_elements=["provider"],
                    set_={"is_enabled": is_enabled},
                )
            )
            db.execute(stmt)

        db.commit()

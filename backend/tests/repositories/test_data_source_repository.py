"""
Tests for DataSourceRepository.

Regression coverage for the ``data_source.source`` column width: Apple
HealthKit tags on-device data with a source bundle identifier of the form
``com.apple.health.<UUID>`` (53 chars). This overflowed the previous
``VARCHAR(50)`` and aborted the entire SDK import batch with
``StringDataRightTruncation``, so no Apple sleep/records were ever saved.
The column is now ``VARCHAR(100)``.
"""

from sqlalchemy.orm import Session

from app.models import DataSource
from app.repositories.data_source_repository import DataSourceRepository
from app.schemas.enums import DeviceType, ProviderName
from tests.factories import UserFactory

# Realistic Apple HealthKit source bundle id: "com.apple.health." + a UUID.
APPLE_HEALTH_SOURCE = "com.apple.health.ED447642-08FD-4E45-AF20-633C02C83170"


class TestDataSourceRepository:
    """Test suite for DataSourceRepository."""

    def test_apple_health_source_bundle_id_persists(self, db: Session) -> None:
        """A 53-char Apple source bundle id imports without truncation.

        Exercises ``ensure_data_source`` (the SDK import path that failed) and
        asserts the full identifier round-trips — this would raise
        ``StringDataRightTruncation`` against the old ``VARCHAR(50)`` column.
        """
        # Arrange: a source longer than the old 50-char limit.
        assert len(APPLE_HEALTH_SOURCE) > 50
        user = UserFactory()
        repo = DataSourceRepository(DataSource)

        # Act
        created = repo.ensure_data_source(
            db,
            user_id=user.id,
            provider=ProviderName.APPLE,
            device_model="Watch7,5",
            source=APPLE_HEALTH_SOURCE,
        )
        db.commit()
        db.expire_all()

        # Assert: stored intact, retrievable by its full identity.
        assert created.source == APPLE_HEALTH_SOURCE
        stored = repo.get_by_identity(
            db,
            user_id=user.id,
            provider=ProviderName.APPLE,
            device_model="Watch7,5",
            source=APPLE_HEALTH_SOURCE,
        )
        assert stored is not None
        assert stored.source == APPLE_HEALTH_SOURCE
        assert len(stored.source) == len(APPLE_HEALTH_SOURCE)

    def test_sdk_device_type_upgrades_from_other_but_never_flips(self, db: Session) -> None:
        user = UserFactory()
        repo = DataSourceRepository(DataSource)
        identity = {
            "user_id": user.id,
            "provider": ProviderName.SAMSUNG,
            "device_model": "unlisted-model",
            "source": "tab",
        }
        created = repo.ensure_data_source(db, **identity)
        assert created.device_type == DeviceType.OTHER

        repo.ensure_data_source(db, **identity, reported_type=DeviceType.WATCH)
        assert repo.get_by_identity(db, **identity).device_type == DeviceType.WATCH

        repo.batch_ensure_data_sources(
            db,
            ProviderName.SAMSUNG,
            None,
            {(user.id, "unlisted-model", "tab", None, None)},
            {(user.id, "unlisted-model", "tab", None, None): DeviceType.BAND},
        )
        assert repo.get_by_identity(db, **identity).device_type == DeviceType.WATCH

    def test_cloud_device_type_is_corrected_on_sync(self, db: Session) -> None:
        user = UserFactory()
        repo = DataSourceRepository(DataSource)
        identity = {
            "user_id": user.id,
            "provider": ProviderName.GARMIN,
            "device_model": "Garmin Index BPM",
            "source": "garmin",
        }
        stored = repo.ensure_data_source(db, **identity)
        object.__setattr__(stored, "device_type", DeviceType.SCALE.value)
        db.flush()

        repo.ensure_data_source(db, **identity)
        assert repo.get_by_identity(db, **identity).device_type == DeviceType.BP_MONITOR

    def test_batch_upgrades_unset_device_type(self, db: Session) -> None:
        user = UserFactory()
        repo = DataSourceRepository(DataSource)
        identity = (user.id, None, "com.fitbit.FitbitMobile", None, None)
        repo.batch_ensure_data_sources(db, ProviderName.HEALTH_CONNECT, None, {identity})
        ds = repo.get_by_identity(db, user.id, ProviderName.HEALTH_CONNECT, None, "com.fitbit.FitbitMobile")
        assert ds.device_type is None

        repo.batch_ensure_data_sources(db, ProviderName.HEALTH_CONNECT, None, {identity}, {identity: DeviceType.BAND})
        db.expire_all()
        ds = repo.get_by_identity(db, user.id, ProviderName.HEALTH_CONNECT, None, "com.fitbit.FitbitMobile")
        assert ds.device_type == DeviceType.BAND

    def test_batch_resolves_stored_empty_model_and_stores_software_version(self, db: Session) -> None:
        user = UserFactory()
        repo = DataSourceRepository(DataSource)
        stored = repo.ensure_data_source(
            db, user_id=user.id, provider=ProviderName.STRAVA, device_model="", source="strava"
        )
        identity = (user.id, None, "strava", None, None)
        new_identity = (user.id, "SM-L315F", "Galaxy Watch7", None, None)

        result = repo.batch_ensure_data_sources(db, ProviderName.STRAVA, None, {identity})
        repo.batch_ensure_data_sources(db, ProviderName.SAMSUNG, None, {new_identity}, None, {new_identity: "5.0.1"})

        assert result[identity] == stored.id
        created = repo.get_by_identity(db, user.id, ProviderName.SAMSUNG, "SM-L315F", "Galaxy Watch7")
        assert created.software_version == "5.0.1"

    def test_device_id_links_records_and_fills_model(self, db: Session) -> None:
        user = UserFactory()
        repo = DataSourceRepository(DataSource)
        sleep = repo.ensure_data_source(
            db, user_id=user.id, provider=ProviderName.POLAR, source="polar", device_id="15995F33"
        )
        workout = repo.ensure_data_source(
            db,
            user_id=user.id,
            provider=ProviderName.POLAR,
            device_model="Polar Vantage M3",
            source="polar",
            device_id="15995F33",
        )

        assert workout.id == sleep.id
        assert workout.device_model == "Polar Vantage M3"

    def test_stable_ids_are_stamped_onto_legacy_row(self, db: Session) -> None:
        user = UserFactory()
        repo = DataSourceRepository(DataSource)
        legacy = repo.ensure_data_source(
            db, user_id=user.id, provider=ProviderName.APPLE, device_model="Watch6,2", source="Apple Watch"
        )

        keyed = repo.ensure_data_source(
            db,
            user_id=user.id,
            provider=ProviderName.APPLE,
            device_model="Watch6,2",
            source="Apple Watch",
            source_app_id="com.apple.health.X",
            device_manufacturer="Apple Inc.",
        )
        renamed = repo.ensure_data_source(
            db,
            user_id=user.id,
            provider=ProviderName.APPLE,
            device_model="Watch6,2",
            source="Kuba's Watch",
            source_app_id="com.apple.health.X",
        )

        assert keyed.id == legacy.id == renamed.id
        assert keyed.source_app_id == "com.apple.health.X"
        assert keyed.device_manufacturer == "Apple Inc."

    def test_record_without_ids_joins_the_only_keyed_row_of_its_model(self, db: Session) -> None:
        user = UserFactory()
        repo = DataSourceRepository(DataSource)
        ids = {"user_id": user.id, "provider": ProviderName.SAMSUNG, "device_model": "SM-M127F"}
        keyed = repo.ensure_data_source(
            db, **ids, source="Kamil's M12", device_id="loGXfm78JC", source_app_id="com.sec.android.app.shealth"
        )

        steps = repo.ensure_data_source(db, **ids, source="m12")
        repo.ensure_data_source(
            db, **ids, source="Galaxy M12", device_id="other", source_app_id="com.sec.android.app.shealth"
        )
        ambiguous = repo.ensure_data_source(db, **ids, source="m12")

        assert steps.id == keyed.id
        assert ambiguous.id != keyed.id

    def test_writer_row_learns_model_and_matches_unknown_model(self, db: Session) -> None:
        user = UserFactory()
        repo = DataSourceRepository(DataSource)
        ids = {"user_id": user.id, "provider": ProviderName.HEALTH_CONNECT, "source_app_id": "com.fitbit.FitbitMobile"}

        first = repo.ensure_data_source(db, **ids, source="com.fitbit.FitbitMobile")
        known = repo.ensure_data_source(db, **ids, device_model="Charge 6", source="com.fitbit.FitbitMobile")
        unknown_again = repo.ensure_data_source(db, **ids, source="com.fitbit.FitbitMobile")

        assert first.id == known.id == unknown_again.id
        assert known.device_model == "Charge 6"

    def test_writer_converges_within_one_batch(self, db: Session) -> None:
        user = UserFactory()
        repo = DataSourceRepository(DataSource)
        app = "com.fitbit.FitbitMobile"
        unknown = (user.id, None, app, None, app)
        known = (user.id, "Charge 6", app, None, app)

        result = repo.batch_ensure_data_sources(db, ProviderName.HEALTH_CONNECT, None, {unknown, known})

        assert result[unknown] == result[known]
        assert repo.get_by_identity(db, user.id, ProviderName.HEALTH_CONNECT, "Charge 6", app, None, app) is not None

    def test_writer_with_several_models_keeps_separate_sources(self, db: Session) -> None:
        user = UserFactory()
        repo = DataSourceRepository(DataSource)
        ids = {"user_id": user.id, "provider": ProviderName.HEALTH_CONNECT, "source_app_id": "com.fitbit.FitbitMobile"}

        charge = repo.ensure_data_source(db, **ids, device_model="Charge 6")
        watch = repo.ensure_data_source(db, **ids, device_model="Pixel Watch 2")
        unknown = repo.ensure_data_source(db, **ids)

        assert len({charge.id, watch.id, unknown.id}) == 3

    def test_host_model_is_replaced_by_producer_model(self, db: Session) -> None:
        user = UserFactory()
        repo = DataSourceRepository(DataSource)
        ids = {
            "user_id": user.id,
            "provider": ProviderName.APPLE,
            "source": "Oura",
            "source_app_id": "com.ouraring.oura",
        }

        relayed = repo.ensure_data_source(db, **ids, device_model="iPhone16,1", reported_type=DeviceType.PHONE)
        produced = repo.ensure_data_source(db, **ids, device_model="Oura Ring Gen3")
        old_client = repo.ensure_data_source(db, **ids, device_model="iPhone16,1", reported_type=DeviceType.PHONE)

        assert relayed.id == produced.id == old_client.id
        assert produced.device_model == "Oura Ring Gen3"
        assert produced.device_type == DeviceType.RING

    def test_apple_own_source_keeps_product_type(self, db: Session) -> None:
        user = UserFactory()
        repo = DataSourceRepository(DataSource)
        ids = {"user_id": user.id, "provider": ProviderName.APPLE, "source_app_id": APPLE_HEALTH_SOURCE}

        watch = repo.ensure_data_source(db, **ids, device_model="Watch6,2")
        other = repo.ensure_data_source(db, **ids, device_model="Watch7,5")

        assert watch.id != other.id
        assert watch.device_model == "Watch6,2"

"""Generic CSV import service.

Orchestrates parsing CSV files from various providers and bulk-creating
EventRecords + WorkoutDetails in the database.
"""

from decimal import Decimal
from logging import Logger, getLogger
from uuid import UUID, uuid4

from app.database import DbSession
from app.schemas.model_crud.activities.event_record import EventRecordCreate
from app.schemas.model_crud.activities.event_record_detail import EventRecordDetailCreate
from app.services.event_record_service import event_record_service

from .runkeeper import parse_runkeeper_csv

SUPPORTED_FORMATS = {"runkeeper"}


class CSVImportService:
    """Import workout data from CSV exports of various fitness platforms."""

    def __init__(self, log: Logger | None = None) -> None:
        self.log = log or getLogger(__name__)

    def import_csv(
        self,
        db_session: DbSession,
        content: str | bytes,
        user_id: UUID,
        source_format: str,
    ) -> dict[str, int | str]:
        """Parse a CSV file and bulk-import workouts.

        Args:
            db_session: Database session.
            content: Raw CSV content (bytes or str).
            user_id: The user to import workouts for.
            source_format: One of SUPPORTED_FORMATS (e.g. "runkeeper").

        Returns:
            Dict with ``imported``, ``skipped`` (duplicates), and ``total`` counts.
        """
        if source_format not in SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported CSV format: {source_format}. Supported: {SUPPORTED_FORMATS}")

        workouts = self._parse(content, source_format)
        self.log.info("Parsed %d workouts from %s CSV for user %s", len(workouts), source_format, user_id)

        if not workouts:
            return {"imported": 0, "skipped": 0, "total": 0}

        records: list[EventRecordCreate] = []
        details: dict[UUID, EventRecordDetailCreate] = {}

        for w in workouts:
            record_id = uuid4()

            avg_speed_ms = None
            if w.get("avg_speed_kmh") is not None:
                avg_speed_ms = Decimal(str(w["avg_speed_kmh"])) / Decimal("3.6")

            records.append(
                EventRecordCreate(
                    id=record_id,
                    external_id=w.get("external_id"),
                    source=source_format,
                    source_name=source_format.title(),
                    user_id=user_id,
                    provider=source_format,
                    category="workout",
                    type=w["workout_type"].value,
                    duration_seconds=w.get("duration_seconds"),
                    start_datetime=w["start_datetime"],
                    end_datetime=w["end_datetime"],
                )
            )

            details[record_id] = EventRecordDetailCreate(
                record_id=record_id,
                distance=Decimal(str(w["distance_meters"])) if w.get("distance_meters") is not None else None,
                energy_burned=Decimal(str(w["calories"])) if w.get("calories") is not None else None,
                total_elevation_gain=Decimal(str(w["climb_meters"])) if w.get("climb_meters") is not None else None,
                heart_rate_avg=Decimal(str(w["avg_heart_rate"])) if w.get("avg_heart_rate") is not None else None,
                average_speed=avg_speed_ms,
            )

        inserted_ids = event_record_service.bulk_create(db_session, records)
        db_session.flush()

        details_to_insert = [details[rid] for rid in inserted_ids if rid in details]
        if details_to_insert:
            event_record_service.bulk_create_details(db_session, details_to_insert, detail_type="workout")

        db_session.commit()

        imported = len(inserted_ids)
        skipped = len(records) - imported
        self.log.info(
            "CSV import complete for user %s: %d imported, %d skipped (duplicates), %d total",
            user_id,
            imported,
            skipped,
            len(records),
        )

        return {"imported": imported, "skipped": skipped, "total": len(records)}

    @staticmethod
    def _parse(content: str | bytes, source_format: str) -> list[dict]:
        if source_format == "runkeeper":
            return parse_runkeeper_csv(content)
        raise ValueError(f"No parser for format: {source_format}")


csv_import_service = CSVImportService()

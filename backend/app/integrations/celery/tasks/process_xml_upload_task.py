import os
from logging import getLogger
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from celery import shared_task
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.activity_summary import ActivitySummary
from app.repositories.data_source_repository import DataSourceRepository
from app.schemas.enums import ProviderName
from app.schemas.providers.apple.apple_xml import XMLParseStats
from app.schemas.sync_status import SyncSource, SyncStatus
from app.services import event_record_service
from app.services.apple.apple_xml.xml_service import XMLService
from app.services.apple.healthkit.sleep_service import handle_sleep_data
from app.services.sync_status_service import completed, failed, new_run_id, started
from app.services.timeseries_service import timeseries_service
from app.utils.sentry_helpers import log_and_capture_error
from app.utils.structured_logging import log_structured

log = getLogger(__name__)


@shared_task
def process_xml_upload(file_path: str, filename: str, user_id: str) -> dict[str, Any]:
    """
    Process XML file from shared volume and import to Postgres database.

    Args:
        file_path: Path to the XML file on the shared volume
        filename: Original filename
        user_id: User ID to associate with the data

    Returns:
        Dict with status, message, and import statistics
    """
    try:
        user_uuid: UUID | None = UUID(user_id)
    except (ValueError, TypeError):
        user_uuid = None

    run_id = new_run_id(prefix="xml")
    if user_uuid is not None:
        started(
            user_uuid,
            "apple",
            SyncSource.XML_IMPORT,
            run_id=run_id,
            message=f"Importing Apple Health XML file {filename}",
            metadata={"filename": filename},
        )

    with SessionLocal() as db:
        try:
            stats = _import_xml_data(db, file_path, user_id)

            if user_uuid is not None:
                completed(
                    user_uuid,
                    "apple",
                    SyncSource.XML_IMPORT,
                    run_id=run_id,
                    status=SyncStatus.SUCCESS,
                    message="Apple Health XML import completed",
                    items_processed=stats.records.processed + stats.workouts.processed + stats.sleep.processed,
                    metadata={"filename": filename},
                )

            return {
                "user_id": user_id,
                "status": "success",
                "message": "Import completed successfully",
                "stats": {
                    "records_processed": stats.records.processed,
                    "records_skipped": stats.records.skipped,
                    "workouts_processed": stats.workouts.processed,
                    "workouts_skipped": stats.workouts.skipped,
                    "sleep_processed": stats.sleep.processed,
                    "sleep_skipped": stats.sleep.skipped,
                    "activity_summaries_processed": stats.activity_summaries.processed,
                    "activity_summaries_skipped": stats.activity_summaries.skipped,
                    "skip_reasons": stats.get_skip_summary(),
                },
            }

        except Exception as e:
            db.rollback()
            if user_uuid is not None:
                failed(
                    user_uuid,
                    "apple",
                    SyncSource.XML_IMPORT,
                    run_id=run_id,
                    error=str(e),
                    message=f"Apple Health XML import failed: {filename}",
                    metadata={"filename": filename},
                )
            log_structured(
                log,
                "error",
                "Failed to import XML file %s for user %s",
                provider="apple_xml",
                task="process_xml_upload",
                filename=filename,
                user_id=user_id,
            )
            log_and_capture_error(
                e,
                log,
                "Failed to import XML file %s for user %s",
                extra={"filename": filename, "user_id": user_id},
            )
            raise e

        finally:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)


def _import_xml_data(db: Session, xml_path: str, user_id: str) -> XMLParseStats:
    """
    Parse XML file and import data to database using XMLService.

    Args:
        db: Database session
        xml_path: Path to the XML file
        user_id: User ID to associate with the data

    Returns:
        XMLParseStats with parsing statistics
    """
    xml_service = XMLService(Path(xml_path), log)

    for time_series_records, workouts, sync_request in xml_service.parse_xml(user_id):
        for record, detail in workouts:
            try:
                created_record = event_record_service.create(db, record)
                detail_for_record = detail.model_copy(update={"record_id": created_record.id})
                event_record_service.create_detail(db, detail_for_record)
            except Exception as e:
                log_structured(
                    log,
                    "warning",
                    "Failed to save workout record %s: %s - skipping",
                    provider="apple_xml",
                    task="process_xml_upload",
                    record_type=record.type if hasattr(record, "type") else "unknown",
                    error=str(e),
                )
                log_and_capture_error(
                    e,
                    log,
                    "Failed to save workout record %s: %s - skipping",
                    extra={"record_type": record.type if hasattr(record, "type") else "unknown", "user_id": user_id},
                )
                xml_service.stats.workouts.skip(f"db_error:{type(e).__name__}")

        if time_series_records:
            timeseries_service.bulk_create_samples(db, time_series_records)
            db.commit()

        if sync_request and sync_request.data.sleep:
            handle_sleep_data(db, sync_request, user_id)

    # Write ActivitySummary rows after all chunks are consumed
    if xml_service.activity_summaries:
        _save_activity_summaries(db, xml_service.activity_summaries, user_id)

    return xml_service.stats


def _save_activity_summaries(
    db: Session,
    summaries: list[dict],
    user_id: str,
) -> None:
    """Bulk-upsert ActivitySummary rows.

    Resolves (or creates) the apple no-device data_source, then inserts
    all summaries with ON CONFLICT DO UPDATE on (data_source_id, date).
    """
    ds_repo = DataSourceRepository()
    data_source = ds_repo.ensure_data_source(
        db,
        user_id=UUID(user_id),
        provider=ProviderName.APPLE,
        user_connection_id=None,
    )

    values_list = []
    for s in summaries:
        values_list.append({
            "id": uuid4(),
            "data_source_id": data_source.id,
            "date": s["date"],
            "active_energy_burned": s["active_energy_burned"],
            "active_energy_burned_goal": s["active_energy_burned_goal"],
            "active_energy_burned_unit": s["active_energy_burned_unit"],
            "apple_move_time": s["apple_move_time"],
            "apple_move_time_goal": s["apple_move_time_goal"],
            "apple_exercise_time": s["apple_exercise_time"],
            "apple_exercise_time_goal": s["apple_exercise_time_goal"],
            "apple_stand_hours": s["apple_stand_hours"],
            "apple_stand_hours_goal": s["apple_stand_hours_goal"],
        })

    # Deduplicate within the batch (keep last value per date)
    deduped: dict[object, dict] = {}
    for v in values_list:
        deduped[(v["data_source_id"], v["date"])] = v
    values_list = list(deduped.values())

    stmt = insert(ActivitySummary).values(values_list)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_activity_summary_source_date",
        set_={
            "active_energy_burned": stmt.excluded.active_energy_burned,
            "active_energy_burned_goal": stmt.excluded.active_energy_burned_goal,
            "active_energy_burned_unit": stmt.excluded.active_energy_burned_unit,
            "apple_move_time": stmt.excluded.apple_move_time,
            "apple_move_time_goal": stmt.excluded.apple_move_time_goal,
            "apple_exercise_time": stmt.excluded.apple_exercise_time,
            "apple_exercise_time_goal": stmt.excluded.apple_exercise_time_goal,
            "apple_stand_hours": stmt.excluded.apple_stand_hours,
            "apple_stand_hours_goal": stmt.excluded.apple_stand_hours_goal,
        },
    )
    db.execute(stmt)
    db.commit()

    log_structured(
        log,
        "info",
        "ActivitySummary upsert complete",
        provider="apple_xml",
        task="process_xml_upload",
        rows=len(values_list),
    )

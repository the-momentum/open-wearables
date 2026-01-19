import json
from datetime import datetime
from decimal import Decimal
from logging import Logger, getLogger
from typing import Iterable
from uuid import UUID, uuid4

from app.database import DbSession
from app.schemas import (
    AEWorkoutJSON,
    EventRecordCreate,
    EventRecordDetailCreate,
    EventRecordMetrics,
    HeartRateSampleCreate,
    RootJSON,
    UploadDataResponse,
)
from app.services.event_record_service import event_record_service
from app.services.timeseries_service import timeseries_service
from app.utils.exceptions import handle_exceptions
from app.utils.sentry_helpers import log_and_capture_error

APPLE_DT_FORMAT = "%Y-%m-%d %H:%M:%S %z"


class ImportService:
    def __init__(self, log: Logger):
        self.log = log
        self.event_record_service = event_record_service
        self.timeseries_service = timeseries_service

    def _dt(self, s: str) -> datetime:
        s = s.replace(" +", "+").replace(" ", "T", 1)
        if len(s) >= 5 and (s[-5] in {"+", "-"} and s[-3] != ":"):
            s = f"{s[:-2]}:{s[-2:]}"
        return datetime.fromisoformat(s)

    def _dec(self, x: float | int | None) -> Decimal | None:
        return None if x is None else Decimal(str(x))

    def _compute_metrics(self, workout: AEWorkoutJSON) -> EventRecordMetrics:
        hr_entries = workout.heartRateData or []

        hr_min_candidates = [self._dec(entry.min) for entry in hr_entries if entry.min is not None]
        hr_max_candidates = [self._dec(entry.max) for entry in hr_entries if entry.max is not None]
        hr_avg_candidates = [self._dec(entry.avg) for entry in hr_entries if entry.avg is not None]

        heart_rate_min = min(hr_min_candidates) if hr_min_candidates else None
        heart_rate_max = max(hr_max_candidates) if hr_max_candidates else None
        heart_rate_avg = (
            sum(hr_avg_candidates, Decimal("0")) / Decimal(len(hr_avg_candidates)) if hr_avg_candidates else None
        )

        return {
            "heart_rate_min": int(heart_rate_min) if heart_rate_min is not None else None,
            "heart_rate_max": int(heart_rate_max) if heart_rate_max is not None else None,
            "heart_rate_avg": heart_rate_avg,
            "steps_count": None,
        }

    def _get_records(
        self,
        workout: AEWorkoutJSON,
        user_id: UUID,
    ) -> list[HeartRateSampleCreate]:
        samples: list[HeartRateSampleCreate] = []

        heart_rate_fields = ("heartRate", "heartRateRecovery")
        for field in heart_rate_fields:
            entries = getattr(workout, field, None)
            if not entries:
                continue

            for entry in entries:
                value = entry.avg or entry.max or entry.min or 0
                source_name = getattr(entry, "source", None) or "Auto Export"
                samples.append(
                    HeartRateSampleCreate(
                        id=uuid4(),
                        external_id=None,
                        user_id=user_id,
                        provider_name="Apple",
                        device_id=source_name,
                        recorded_at=self._dt(entry.date),
                        value=self._dec(value) or 0,
                    ),
                )

        return samples

    def _build_import_bundles(
        self,
        raw: dict,
        user_id: str,
    ) -> Iterable[tuple[EventRecordCreate, EventRecordDetailCreate, list[HeartRateSampleCreate]]]:
        """
        Given the parsed JSON dict from HealthAutoExport, yield ImportBundles
        ready to insert the database.
        """
        root = RootJSON(**raw)
        workouts_raw = root.data.get("workouts", [])

        user_uuid = UUID(user_id)
        for w in workouts_raw:
            wjson = AEWorkoutJSON(**w)

            workout_id = uuid4()

            start_date = self._dt(wjson.start)
            end_date = self._dt(wjson.end)
            duration_seconds = int((end_date - start_date).total_seconds())

            metrics = self._compute_metrics(wjson)
            hr_samples = self._get_records(wjson, user_uuid)

            workout_type = wjson.name or "Unknown Workout"

            record = EventRecordCreate(
                category="workout",
                type=workout_type,
                source_name="Auto Export",
                device_id=None,
                duration_seconds=duration_seconds,
                start_datetime=start_date,
                end_datetime=end_date,
                id=workout_id,
                external_id=wjson.id,
                provider_name="Apple",
                user_id=user_uuid,
            )

            detail = EventRecordDetailCreate(
                record_id=workout_id,
                **metrics,
            )

            yield record, detail, hr_samples

    def load_data(self, db_session: DbSession, raw: dict, user_id: str) -> bool:
        # Collect all HR samples from all workouts for a single batch insert
        all_hr_samples: list[HeartRateSampleCreate] = []

        for record, detail, hr_samples in self._build_import_bundles(raw, user_id):
            created_record = self.event_record_service.create(db_session, record)
            detail_for_record = detail.model_copy(update={"record_id": created_record.id})
            self.event_record_service.create_detail(db_session, detail_for_record)

            if hr_samples:
                all_hr_samples.extend(hr_samples)

        # Single batch insert for all HR samples
        if all_hr_samples:
            self.timeseries_service.bulk_create_samples(db_session, all_hr_samples)

        return True

    @handle_exceptions
    def import_data_from_request(
        self,
        db_session: DbSession,
        request_content: str,
        content_type: str,
        user_id: str,
    ) -> UploadDataResponse:
        try:
            # Parse content based on type
            if "multipart/form-data" in content_type:
                data = self._parse_multipart_content(request_content)
            else:
                data = self._parse_json_content(request_content)

            if not data:
                return UploadDataResponse(status_code=400, response="No valid data found", user_id=user_id)

            # Load data using provided database session
            self.load_data(db_session, data, user_id=user_id)

        except Exception as e:
            log_and_capture_error(e, self.log, f"Import failed for user {user_id}: {e}", extra={"user_id": user_id})
            return UploadDataResponse(status_code=400, response=f"Import failed: {str(e)}", user_id=user_id)

        return UploadDataResponse(status_code=200, response="Import successful", user_id=user_id)

    def _parse_multipart_content(self, content: str) -> dict | None:
        """Parse multipart form data to extract JSON."""
        json_start = content.find('{\n  "data"')
        if json_start == -1:
            json_start = content.find('{"data"')
        if json_start == -1:
            return None

        brace_count = 0
        json_end = json_start
        for i, char in enumerate(content[json_start:], json_start):
            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0:
                    json_end = i
                    break

        if brace_count != 0:
            return None

        json_str = content[json_start : json_end + 1]
        return json.loads(json_str)

    def _parse_json_content(self, content: str) -> dict | None:
        """Parse JSON content directly."""
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return None


import_service = ImportService(log=getLogger(__name__))

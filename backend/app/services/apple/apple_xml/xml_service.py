from datetime import datetime
from decimal import Decimal, InvalidOperation
from logging import Logger
from pathlib import Path
from typing import Any, Generator
from uuid import UUID, uuid4
from xml.etree import ElementTree as ET

from app.config import settings
from app.constants.series_types.apple import SleepPhase, get_series_type_from_metric_type
from app.constants.workout_types import get_unified_apple_workout_type_xml
from app.schemas import (
    EventRecordCreate,
    EventRecordDetailCreate,
    EventRecordMetrics,
    HeartRateSampleCreate,
    SeriesType,
    StepSampleCreate,
    TimeSeriesSampleCreate,
)
from app.schemas.apple.apple_xml.stats import XMLParseStats
from app.schemas.apple.healthkit.sync_request import (
    SleepRecord,
    SourceInfo,
    SyncRequest,
    SyncRequestData,
)
from app.utils.structured_logging import log_structured


class XMLService:
    def __init__(self, path: Path, log: Logger):
        self.xml_path: Path = path
        self.chunk_size: int = settings.xml_chunk_size
        self.log: Logger = log
        self.stats: XMLParseStats = XMLParseStats()

    DATE_FIELDS: tuple[str, ...] = ("startDate", "endDate", "creationDate")
    RECORD_COLUMNS: tuple[str, ...] = (
        "type",
        "sourceVersion",
        "sourceName",
        "device",
        "startDate",
        "endDate",
        "creationDate",
        "unit",
        "value",
        "textValue",
    )
    WORKOUT_COLUMNS: tuple[str, ...] = (
        "type",
        "duration",
        "durationUnit",
        "sourceName",
        "startDate",
        "endDate",
    )
    WORKOUT_STATS_COLUMNS: tuple[str, ...] = (
        "type",
        "startDate",
        "endDate",
        "sum",
        "average",
        "maximum",
        "minimum",
        "unit",
    )
    SLEEP_VALUE_TO_STAGE: dict[str, SleepPhase] = {
        "HKCategoryValueSleepAnalysisAsleepCore": SleepPhase.ASLEEP_LIGHT,
        "HKCategoryValueSleepAnalysisAsleepDeep": SleepPhase.ASLEEP_DEEP,
        "HKCategoryValueSleepAnalysisAsleepREM": SleepPhase.ASLEEP_REM,
        "HKCategoryValueSleepAnalysisAwake": SleepPhase.AWAKE,
        "HKCategoryValueSleepAnalysisInBed": SleepPhase.IN_BED,
        "HKCategoryValueSleepAnalysisAsleep": SleepPhase.SLEEPING,
        "HKCategoryValueSleepAnalysisAsleepUnspecified": SleepPhase.SLEEPING,
    }

    def _parse_date_fields(self, document: dict[str, Any]) -> dict[str, Any]:
        for date_field in self.DATE_FIELDS:
            if date_field in document:
                try:
                    document[date_field] = datetime.strptime(document[date_field], "%Y-%m-%d %H:%M:%S %z")
                except ValueError as e:
                    raise ValueError(f"Invalid date format for field {date_field}: {document[date_field]}") from e
        return document

    def _parse_decimal_value(self, raw_value: str | None, metric_type: str) -> Decimal | None:
        """Safely parse a decimal value from string.

        Returns None if the value cannot be parsed, logging a warning with context.
        """
        if raw_value is None:
            self.log.debug("Missing value for metric type %s", metric_type)
            return None

        # Handle empty strings
        if not raw_value.strip():
            self.log.debug("Empty value for metric type %s", metric_type)
            return None

        try:
            return Decimal(raw_value)
        except InvalidOperation:
            self.log.warning(
                "Invalid decimal value '%s' for metric type %s (conversion syntax error)",
                raw_value[:50] if len(raw_value) > 50 else raw_value,
                metric_type,
            )
            return None
        except (ValueError, ArithmeticError) as e:
            self.log.warning(
                "Failed to parse decimal value '%s' for metric type %s: %s",
                raw_value[:50] if len(raw_value) > 50 else raw_value,
                metric_type,
                str(e),
            )
            return None

    def _extract_device_info(self, raw_source: str | None) -> SourceInfo:
        """
        Extract device information from source info.
        Example device string: device="<<HKDevice: 0x66aaba640>,
          name:Apple Watch, manufacturer:Apple Inc., model:Watch,
          hardware:Watch6,12, software:26.2, creation date:2026-01-15 22:56:09 +0000>"
        Mobile SDK extracts more info about device, but XML exposes
          only the fields above.
        """
        if not raw_source:
            return SourceInfo()

        source_list = raw_source.strip("<>").split(", ")
        raw_fields: dict[str, str] = {}
        for part in source_list:
            if ":" not in part:
                continue
            key, value = part.split(":", maxsplit=1)
            raw_fields[key.strip()] = value.strip()

        return SourceInfo(
            name=raw_fields.get("name"),
            device_id=raw_fields.get("device"),
            device_model=raw_fields.get("model"),
            device_manufacturer=raw_fields.get("manufacturer"),
            device_hardware_version=raw_fields.get("hardware"),
            device_software_version=raw_fields.get("software"),
        )

    def _normalize_sleep_record(self, document: dict[str, Any]) -> SleepRecord | None:
        """Normalize a sleep record."""
        stage = self.SLEEP_VALUE_TO_STAGE.get(str(document.get("value")))
        if stage is None:
            return None

        start_date = datetime.fromisoformat(str(document.get("startDate")))
        end_date = datetime.fromisoformat(str(document.get("endDate")))

        source_info = self._extract_device_info(document.get("device", ""))

        return SleepRecord(
            id=None,
            parentId=None,
            stage=stage,
            startDate=start_date,
            endDate=end_date,
            source=source_info,
        )

    def _create_record(
        self,
        document: dict[str, Any],
        user_id: UUID,
    ) -> HeartRateSampleCreate | StepSampleCreate | TimeSeriesSampleCreate | None:
        """Create a time series record from an XML document.

        Returns None if the record cannot be created (unsupported type, invalid value, etc.)
        """
        metric_type = document.get("type", "")
        series_type = get_series_type_from_metric_type(metric_type)

        # Skip unsupported metric types early (this is normal, not an error)
        if series_type is None:
            return None

        # Parse the value - skip record if invalid
        value = self._parse_decimal_value(document.get("value"), metric_type)
        if value is None:
            self.stats.records.skip(f"invalid_value:{metric_type}")
            return None

        # Parse date fields
        try:
            document = self._parse_date_fields(document)
        except ValueError as e:
            self.log.warning("Failed to parse date for metric type %s: %s", metric_type, str(e))
            self.stats.records.skip(f"invalid_date:{metric_type}")
            return None

        # Check required date field
        if "startDate" not in document:
            self.log.warning("Missing startDate for metric type %s", metric_type)
            self.stats.records.skip(f"missing_startDate:{metric_type}")
            return None

        device_info = self._extract_device_info(document.get("device", ""))

        sample = TimeSeriesSampleCreate(
            id=uuid4(),
            external_id=None,
            user_id=user_id,
            source="apple_health_xml",
            device_model=device_info.device_model,
            software_version=device_info.device_software_version,
            recorded_at=document["startDate"],
            value=value,
            series_type=series_type,
        )

        match series_type:
            case SeriesType.heart_rate:
                return HeartRateSampleCreate(**sample.model_dump())
            case SeriesType.steps:
                return StepSampleCreate(**sample.model_dump())
            case _:
                return sample

    def _create_workout(
        self,
        document: dict[str, Any],
        user_id: UUID,
        metrics: EventRecordMetrics | None = None,
    ) -> tuple[EventRecordCreate, EventRecordDetailCreate]:
        document = self._parse_date_fields(document)

        workout_id = uuid4()
        raw_type = document.pop("workoutActivityType")

        workout_type = get_unified_apple_workout_type_xml(raw_type)

        device_info = self._extract_device_info(document.get("device", ""))

        duration_seconds = int((document["endDate"] - document["startDate"]).total_seconds())

        record = EventRecordCreate(
            category="workout",
            type=workout_type.value,
            source_name=document["sourceName"],
            device_model=device_info.device_model,
            software_version=device_info.device_software_version,
            duration_seconds=duration_seconds,
            start_datetime=document["startDate"],
            end_datetime=document["endDate"],
            external_id=None,
            id=workout_id,
            source="apple_health_xml",
            user_id=user_id,
        )

        actual_metrics = metrics if metrics is not None else self._init_metrics()
        detail = EventRecordDetailCreate(
            record_id=workout_id,
            **actual_metrics,
        )

        return record, detail

    def _init_metrics(self) -> EventRecordMetrics:
        return {
            "energy_burned": Decimal("0"),
            "heart_rate_min": None,
            "heart_rate_max": None,
            "heart_rate_avg": None,
            "steps_count": None,
        }

    def _decimal_from_stat(self, value: str | None) -> Decimal | None:
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (ValueError, ArithmeticError):
            return None

    def _update_metrics_from_stat(self, metrics: EventRecordMetrics, statistic: dict[str, Any]) -> None:
        stat_type = statistic.get("type", "")
        if not stat_type:
            return
        lowered = stat_type.lower()

        min_value = self._decimal_from_stat(statistic.get("minimum"))
        max_value = self._decimal_from_stat(statistic.get("maximum"))
        avg_value = self._decimal_from_stat(statistic.get("average"))

        if "heart" in lowered:
            if min_value is not None:
                metrics["heart_rate_min"] = int(min_value)
            if max_value is not None:
                metrics["heart_rate_max"] = int(max_value)
            if avg_value is not None:
                metrics["heart_rate_avg"] = avg_value

        if "energyburned" in lowered and metrics["energy_burned"] is not None:
            metrics["energy_burned"] += self._decimal_from_stat(statistic.get("sum")) or Decimal("0")

    def _wrap_sleep_data(self, sleep_records: list[SleepRecord]) -> SyncRequest:
        """Wrap sleep data in a SyncRequest
        to be sent to the handle_sleep_data function."""
        return SyncRequest(
            provider="apple_health_xml",
            sdkVersion="n/a",
            syncTimestamp=datetime.now(),
            data=SyncRequestData(
                sleep=sleep_records,
                records=[],
                workouts=[],
            ),
        )

    def parse_xml(
        self,
        user_id: str,
    ) -> Generator[
        tuple[
            list[TimeSeriesSampleCreate],
            list[tuple[EventRecordCreate, EventRecordDetailCreate]],
            SyncRequest,
        ],
        None,
        None,
    ]:
        """
        Parses the XML file and yields tuples of workouts and statistics.
        Extracts attributes from each Record/Workout element.

        Invalid records are skipped with warnings logged. Stats are tracked
        and can be accessed via self.stats after parsing.

        Args:
            user_id: User ID to associate with parsed records
        """
        time_series_records: list[TimeSeriesSampleCreate] = []
        workouts: list[tuple[EventRecordCreate, EventRecordDetailCreate]] = []
        sleep_records: list[SleepRecord] = []

        uuid_user = UUID(user_id)

        # Reset stats for this parse run
        self.stats = XMLParseStats()

        for event, elem in ET.iterparse(self.xml_path, events=("end",)):
            if elem.tag == "Record" and event == "end":
                if len(workouts) + len(time_series_records) + len(sleep_records) >= self.chunk_size:
                    self.log.info(
                        "Yielding chunk: %s time series records, %s workouts, %s sleep records \
                            (skipped so far: %s records, %s workouts, %s sleep records)",
                        len(time_series_records),
                        len(workouts),
                        len(sleep_records),
                        self.stats.records.skipped,
                        self.stats.workouts.skipped,
                        self.stats.sleep.skipped,
                    )
                    sync_request = self._wrap_sleep_data(sleep_records)
                    yield time_series_records, workouts, sync_request
                    time_series_records = []
                    workouts = []
                    sleep_records = []

                try:
                    record: dict[str, Any] = elem.attrib.copy()

                    # Handle sleep records
                    if record.get("type") == "HKCategoryTypeIdentifierSleepAnalysis":
                        sleep_record = self._normalize_sleep_record(record)
                        if sleep_record is not None:
                            sleep_records.append(sleep_record)
                            self.stats.sleep.mark_processed()
                        else:
                            self.log.warning(
                                "Skipping sleep record with unsupported stage %s",
                                record.get("value"),
                            )
                            self.stats.sleep.skip(f"unknown_sleep_stage:{record.get('value')}")
                        elem.clear()
                        continue

                    record_create = self._create_record(record, uuid_user)
                    if record_create is not None:
                        time_series_records.append(record_create)
                        self.stats.records.mark_processed()
                except Exception as e:
                    # Catch any unexpected errors to prevent entire import from failing
                    metric_type = elem.attrib.get("type", "unknown")
                    self.log.warning(
                        "Unexpected error parsing record of type %s: %s - skipping",
                        metric_type,
                        str(e),
                    )
                    self.stats.records.skip(f"unexpected_error:{type(e).__name__}")
                finally:
                    elem.clear()

            elif elem.tag == "Workout" and event == "end":
                if len(workouts) + len(time_series_records) >= self.chunk_size:
                    self.log.info(
                        "Yielding chunk: %s time series records, %s workouts (skipped so far: %s records, %s workouts)",
                        len(time_series_records),
                        len(workouts),
                        self.stats.records.skipped,
                        self.stats.workouts.skipped,
                    )
                    sync_request = self._wrap_sleep_data(sleep_records)
                    yield time_series_records, workouts, sync_request
                    time_series_records = []
                    workouts = []
                    sleep_records = []

                try:
                    workout_data: dict[str, Any] = elem.attrib.copy()
                    metrics = self._init_metrics()
                    for stat in elem:
                        if stat.tag != "WorkoutStatistics":
                            continue
                        statistic = stat.attrib.copy()
                        self._update_metrics_from_stat(metrics, statistic)
                    workout_record, workout_detail = self._create_workout(workout_data, uuid_user, metrics)
                    workouts.append((workout_record, workout_detail))
                    self.stats.workouts.mark_processed()
                except Exception as e:
                    # Catch any unexpected errors to prevent entire import from failing
                    workout_type = elem.attrib.get("workoutActivityType", "unknown")
                    self.log.warning(
                        "Unexpected error parsing workout of type %s: %s - skipping",
                        workout_type,
                        str(e),
                    )
                    self.stats.workouts.skip(f"unexpected_error:{type(e).__name__}")
                finally:
                    elem.clear()

        # yield remaining records and workout pairs
        log_structured(
            self.log,
            "info",
            "Final chunk",
            provider="apple_xml",
            task="process_xml_upload",
            record_count=len(time_series_records),
            workout_count=len(workouts),
            sleep_count=len(sleep_records),
        )
        sync_request = self._wrap_sleep_data(sleep_records)
        yield time_series_records, workouts, sync_request

        # Log final stats
        self._log_parse_summary()

    def _log_parse_summary(self) -> None:
        """Log a summary of the parsing results."""
        total_records = self.stats.records.processed + self.stats.records.skipped
        total_workouts = self.stats.workouts.processed + self.stats.workouts.skipped
        total_sleep = self.stats.sleep.processed + self.stats.sleep.skipped

        log_structured(
            self.log,
            "info",
            "XML parsing complete",
            provider="apple_xml",
            task="process_xml_upload",
            records_processed=self.stats.records.processed,
            total_records=total_records,
            workouts_processed=self.stats.workouts.processed,
            total_workouts=total_workouts,
            sleep_processed=self.stats.sleep.processed,
            total_sleep=total_sleep,
        )

        if self.stats.any_skipped():
            log_structured(
                self.log,
                "warning",
                "Records, workouts, or sleep skipped during import",
                provider="apple_xml",
                task="process_xml_upload",
                skipped_records=self.stats.records.skipped,
                skipped_workouts=self.stats.workouts.skipped,
                skipped_sleep=self.stats.sleep.skipped,
            )

            # Log breakdown of skip reasons
            for type, reasons in self.stats.get_skip_summary().items():
                log_structured(
                    self.log,
                    "warning",
                    f"Skipped {type}: {reasons}",
                    provider="apple_xml",
                    task="process_xml_upload",
                    skip_type=type,
                )

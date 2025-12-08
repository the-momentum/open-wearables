from datetime import datetime
from decimal import Decimal
from logging import Logger
from pathlib import Path
from typing import Any, Generator
from uuid import UUID, uuid4
from xml.etree import ElementTree as ET

from app.config import settings
from app.constants.workout_types.apple import get_unified_workout_type
from app.schemas import (
    EventRecordCreate,
    EventRecordDetailCreate,
    EventRecordMetrics,
    HeartRateSampleCreate,
    StepSampleCreate,
)
from app.constants.workout_types.apple import get_unified_workout_type


class XMLService:
    def __init__(self, path: Path, log: Logger):
        self.xml_path: Path = path
        self.chunk_size: int = settings.xml_chunk_size
        self.log: Logger = log

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

    def _parse_date_fields(self, document: dict[str, Any]) -> dict[str, Any]:
        for field in self.DATE_FIELDS:
            if field in document:
                try:
                    document[field] = datetime.strptime(document[field], "%Y-%m-%d %H:%M:%S %z")
                except ValueError as e:
                    raise ValueError(f"Invalid date format for field {field}: {document[field]}") from e
        return document

    def _create_record(
        self,
        document: dict[str, Any],
        user_id: UUID,
    ) -> HeartRateSampleCreate | StepSampleCreate | None:
        document = self._parse_date_fields(document)

        metric_type = document.get("type", "")
        value = Decimal(document["value"])

        if "HKQuantityTypeIdentifierHeartRate" in metric_type:
            return HeartRateSampleCreate(
                id=uuid4(),
                user_id=user_id,
                provider_id=None,
                device_id=document.get("device"),
                recorded_at=document["startDate"],
                value=value,
            )
        if "HKQuantityTypeIdentifierStepCount" in metric_type:
            return StepSampleCreate(
                id=uuid4(),
                user_id=user_id,
                provider_id=None,
                device_id=document.get("device"),
                recorded_at=document["startDate"],
                value=value,
            )

        return None

    def _create_workout(
        self,
        document: dict[str, Any],
        user_id: UUID,
        metrics: EventRecordMetrics | None = None,
    ) -> tuple[EventRecordCreate, EventRecordDetailCreate]:
        document = self._parse_date_fields(document)

        workout_id = uuid4()
        raw_type = document.pop("workoutActivityType")

        workout_type = get_unified_workout_type(raw_type)

        duration_seconds = int((document["endDate"] - document["startDate"]).total_seconds())

        record = EventRecordCreate(
            category="workout",
            type=workout_type.value,
            source_name=document["sourceName"],
            device_id=document.get("device"),
            duration_seconds=duration_seconds,
            start_datetime=document["startDate"],
            end_datetime=document["endDate"],
            id=workout_id,
            provider_id=None,
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
            "heart_rate_min": None,
            "heart_rate_max": None,
            "heart_rate_avg": None,
            "steps_min": None,
            "steps_max": None,
            "steps_avg": None,
            "steps_total": None,
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
        elif "step" in lowered:
            if min_value is not None:
                metrics["steps_min"] = int(min_value)
            if max_value is not None:
                metrics["steps_max"] = int(max_value)
            if avg_value is not None:
                metrics["steps_avg"] = avg_value

    def parse_xml(
        self,
        user_id: str,
    ) -> Generator[
        tuple[
            list[HeartRateSampleCreate],
            list[StepSampleCreate],
            list[tuple[EventRecordCreate, EventRecordDetailCreate]],
        ],
        None,
        None,
    ]:
        """
        Parses the XML file and yields tuples of workouts and statistics.
        Extracts attributes from each Record/Workout element.

        Args:
            user_id: User ID to associate with parsed records
        """
        heart_rate_records: list[HeartRateSampleCreate] = []
        step_records: list[StepSampleCreate] = []
        workouts: list[tuple[EventRecordCreate, EventRecordDetailCreate]] = []
        uuid_user = UUID(user_id)

        for event, elem in ET.iterparse(self.xml_path, events=("end",)):
            if elem.tag == "Record" and event == "end":
                if len(workouts) + len(heart_rate_records) + len(step_records) >= self.chunk_size:
                    self.log.info(
                        "Lengths of records, workouts: %s, %s, %s",
                        len(heart_rate_records),
                        len(step_records),
                        len(workouts),
                    )
                    yield heart_rate_records, step_records, workouts
                    heart_rate_records = []
                    step_records = []
                    workouts = []
                record: dict[str, Any] = elem.attrib.copy()
                record_create = self._create_record(record, uuid_user)
                if isinstance(record_create, HeartRateSampleCreate):
                    heart_rate_records.append(record_create)
                elif isinstance(record_create, StepSampleCreate):
                    step_records.append(record_create)
                elem.clear()

            elif elem.tag == "Workout" and event == "end":
                if len(workouts) + len(heart_rate_records) + len(step_records) >= self.chunk_size:
                    self.log.info(
                        "Lengths of records, workouts: %s, %s, %s",
                        len(heart_rate_records),
                        len(step_records),
                        len(workouts),
                    )
                    yield heart_rate_records, step_records, workouts
                    heart_rate_records = []
                    step_records = []
                    workouts = []
                workout: dict[str, Any] = elem.attrib.copy()
                metrics = self._init_metrics()
                for stat in elem:
                    if stat.tag != "WorkoutStatistics":
                        continue
                    statistic = stat.attrib.copy()
                    self._update_metrics_from_stat(metrics, statistic)
                workout_record, workout_detail = self._create_workout(workout, uuid_user, metrics)
                workouts.append((workout_record, workout_detail))
                elem.clear()

        # yield remaining records and workout pairs
        self.log.info(
            "Lengths of records, workouts: %s, %s, %s",
            len(heart_rate_records),
            len(step_records),
            len(workouts),
        )
        yield heart_rate_records, step_records, workouts

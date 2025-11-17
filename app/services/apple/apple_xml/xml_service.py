from datetime import datetime
from pathlib import Path
from typing import Any, Generator
from uuid import uuid4, UUID
from xml.etree import ElementTree as ET

from app.schemas import HKWorkoutStatisticCreate, HKWorkoutCreate, HKRecordCreate
from app.config import settings


class XMLService:
    def __init__(self, path: Path):
        self.xml_path: Path = path
        self.chunk_size: int = settings.xml_chunk_size

    DATE_FIELDS: tuple[str, ...] = ("startDate", "endDate", "creationDate")
    DEFAULT_VALUES: dict[str, str] = {
        "unit": "",
        "sourceVersion": "",
        "device": "",
        "value": "",
    }
    DEFAULT_STATS: dict[str, float] = {
        "sum": 0.0,
        "average": 0.0,
        "maximum": 0.0,
        "minimum": 0.0,
    }
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

    def _create_record(self, document: dict[str, Any], user_id: str = None) -> HKRecordCreate:
        document = self._parse_date_fields(document)

        return HKRecordCreate(
            id=uuid4(),
            user_id=UUID(user_id),
            type=document["type"],
            startDate=document["startDate"],
            endDate=document["endDate"],
            sourceName=document["sourceName"],
            unit=document["unit"],
            value=document["value"],
        )

    def _create_workout(self, document: dict[str, Any], user_id: str = None) -> HKWorkoutCreate:
        document = self._parse_date_fields(document)

        document["type"] = document.pop("workoutActivityType")

        return HKWorkoutCreate(
            id=uuid4(),
            user_id=UUID(user_id),
            type=document["type"],
            duration=document["duration"],
            durationUnit=document["durationUnit"],
            sourceName=document["sourceName"],
            startDate=document["startDate"],
            endDate=document["endDate"],
        )

    def _create_statistic(self, document: dict[str, Any], user_id: str = None) -> list[HKWorkoutStatisticCreate]:
        document = self._parse_date_fields(document)

        statistics: list[HKWorkoutStatisticCreate] = []
        for field in ["sum", "average", "maximum", "minimum"]:
            if field in document:
                statistics.append(
                    HKWorkoutStatisticCreate(
                        id=uuid4(),
                        user_id=UUID(user_id),
                        workout_id=document["workout_id"],
                        type=document["type"],
                        value=document[field],
                        unit=document["unit"],
                    )
                )

        return statistics if statistics else []

    def parse_xml(
        self, user_id: str = None
    ) -> Generator[
        tuple[list[HKRecordCreate], list[tuple[HKWorkoutCreate, list[HKWorkoutStatisticCreate]]]], None, None
    ]:
        """
        Parses the XML file and yields tuples of workouts and statistics.
        Extracts attributes from each Record/Workout element.

        Args:
            user_id: User ID to associate with parsed records
        """
        records: list[HKRecordCreate] = []
        workouts: list[HKWorkoutCreate] = []
        statistics: list[list[HKWorkoutStatisticCreate]] = []

        for event, elem in ET.iterparse(self.xml_path, events=("end",)):
            if elem.tag == "Record" and event == "end":
                if len(records) >= self.chunk_size:
                    yield records, list(zip(workouts, statistics))
                    records = []
                    workouts = []
                    statistics = []
                record: dict[str, Any] = elem.attrib.copy()
                record_create = self._create_record(record, user_id)
                if record_create:
                    records.append(record_create)

            elif elem.tag == "Workout" and event == "end":
                if len(workouts) >= self.chunk_size:
                    yield records, list(zip(workouts, statistics))
                    records = []
                    workouts = []
                    statistics = []
                workout: dict[str, Any] = elem.attrib.copy()
                workout_create: HKWorkoutCreate = self._create_workout(workout, user_id)
                if workout_create:
                    workouts.append(workout_create)

                # append workout statistics to workout
                for stat in elem:
                    if stat.tag != "WorkoutStatistics":
                        continue
                    statistic = stat.attrib.copy()
                    statistic["workout_id"] = workout_create.id
                    statistics.append(self._create_statistic(statistic, user_id))
            elem.clear()

        # yield remaining records and workout pairs
        yield records, list(zip(workouts, statistics))

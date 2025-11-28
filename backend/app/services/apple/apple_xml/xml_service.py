from datetime import datetime
from logging import Logger
from pathlib import Path
from typing import Any, Generator
from uuid import UUID, uuid4
from xml.etree import ElementTree as ET

from app.config import settings
from app.schemas import WorkoutCreate, WorkoutStatisticCreate


class XMLService:
    def __init__(self, path: Path, log: Logger):
        self.xml_path: Path = path
        self.chunk_size: int = settings.xml_chunk_size
        self.log: Logger = log

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

    def _create_record(self, document: dict[str, Any], user_id: str) -> WorkoutStatisticCreate:
        document = self._parse_date_fields(document)

        return WorkoutStatisticCreate(
            id=uuid4(),
            user_id=UUID(user_id),
            workout_id=None,
            type=document["type"],
            start_datetime=document["startDate"],
            end_datetime=document["endDate"],
            min=document["value"],
            max=document["value"],
            avg=document["value"],
            unit=document["unit"],
        )

    def _create_workout(self, document: dict[str, Any], user_id: str) -> WorkoutCreate:
        document = self._parse_date_fields(document)

        document["type"] = document.pop("workoutActivityType")

        duration_seconds = (document["endDate"] - document["startDate"]).total_seconds()

        return WorkoutCreate(
            id=uuid4(),
            provider_id=None,
            user_id=UUID(user_id),
            type=document["type"],
            duration_seconds=duration_seconds,
            source_name=document["sourceName"],
            start_datetime=document["startDate"],
            end_datetime=document["endDate"],
        )

    def _create_statistics(self, document: dict[str, Any], user_id: str) -> list[WorkoutStatisticCreate]:
        document = self._parse_date_fields(document)

        statistics: list[WorkoutStatisticCreate] = []
        for field in ["sum", "average", "maximum", "minimum"]:
            if field in document:
                statistics.append(
                    WorkoutStatisticCreate(
                        id=uuid4(),
                        user_id=UUID(user_id),
                        workout_id=None,
                        type=document["type"],
                        start_datetime=document["startDate"],
                        end_datetime=document["endDate"],
                        min=document[field],
                        max=document[field],
                        avg=document[field],
                        unit=document["unit"],
                    ),
                )

        return statistics if statistics else []

    def parse_xml(
        self,
        user_id: str,
    ) -> Generator[tuple[list[WorkoutStatisticCreate], list[WorkoutCreate], list[WorkoutStatisticCreate]], None, None]:
        """
        Parses the XML file and yields tuples of workouts and statistics.
        Extracts attributes from each Record/Workout element.

        Args:
            user_id: User ID to associate with parsed records
        """
        records: list[WorkoutStatisticCreate] = []
        workouts: list[WorkoutCreate] = []
        statistics: list[WorkoutStatisticCreate] = []

        for event, elem in ET.iterparse(self.xml_path, events=("end",)):
            if elem.tag == "Record" and event == "end":
                if len(workouts) + len(records) + len(statistics) >= self.chunk_size:
                    self.log.info(
                        f"Lengths of records, workouts, statistics: \
                        {len(records)}, {len(workouts)}, {len(statistics)}",
                    )
                    yield records, workouts, statistics
                    records = []
                    workouts = []
                    statistics = []
                record: dict[str, Any] = elem.attrib.copy()
                record_create = self._create_record(record, user_id)
                if record_create:
                    records.append(record_create)
                elem.clear()

            elif elem.tag == "Workout" and event == "end":
                if len(workouts) + len(records) + len(statistics) >= self.chunk_size:
                    self.log.info(
                        f"Lengths of records, workouts, statistics: \
                        {len(records)}, {len(workouts)}, {len(statistics)}",
                    )
                    yield records, workouts, statistics
                    records = []
                    workouts = []
                    statistics = []
                workout: dict[str, Any] = elem.attrib.copy()
                workout_create: WorkoutCreate = self._create_workout(workout, user_id)
                if workout_create:
                    workouts.append(workout_create)

                # append workout statistics to workout
                for stat in elem:
                    if len(workouts) + len(records) + len(statistics) >= self.chunk_size:
                        self.log.info(
                            f"Lengths of records, workouts, statistics: \
                            {len(records)}, {len(workouts)}, {len(statistics)}",
                        )
                        yield records, workouts, statistics
                    if stat.tag != "WorkoutStatistics":
                        continue
                    statistic = stat.attrib.copy()
                    statistic["workout_id"] = str(workout_create.id)
                    statistics.extend(self._create_statistics(statistic, user_id))
                elem.clear()

        # yield remaining records and workout pairs
        self.log.info(f"Lengths of records, workouts, statistics: {len(records)}, {len(workouts)}, {len(statistics)}")
        yield records, workouts, statistics

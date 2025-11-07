from datetime import datetime
from pathlib import Path
from typing import Any, Generator
from uuid import uuid4
from xml.etree import ElementTree as ET

import pandas as pd

from app.schemas import HKWorkoutStatisticCreate, HKWorkoutCreate, HKRecordCreate


class XMLService:
    def __init__(self, path: Path):
        self.xml_path: Path = path
        self.chunk_size: int = 50_000

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

    def update_record(self, kind: str, document: dict[str, Any]) -> HKWorkoutCreate | list[HKWorkoutStatisticCreate] | None:
        """
        change this
        also not update record but something like create record
        """
        for field in self.DATE_FIELDS:
            if field in document:
                document[field] = datetime.strptime(document[field], "%Y-%m-%d %H:%M:%S %z")

        if kind == "record":
            return HKRecordCreate(
                id=uuid4(),
                user_id=document["user_id"],
                type=document["type"],
                startDate=document["startDate"],
                endDate=document["endDate"],
                unit=document["unit"],
                value=document["value"],
            )

        if kind == "workout":
            document["type"] = document.pop("workoutActivityType")

            return HKWorkoutCreate(
                id=uuid4(),
                user_id=document["user_id"],
                type=document["type"],
                duration=document["duration"],
                durationUnit=document["durationUnit"],
                sourceName=document["sourceName"],
                startDate=document["startDate"],
                endDate=document["endDate"],
            )

        if kind == "stat":
            statistics: list[HKWorkoutStatisticCreate] = []
            for field in ['sum', 'average', 'maximum', 'minimum']:
                if field in document:
                    statistics.append(HKWorkoutStatisticCreate(
                        id=uuid4(),
                        user_id=document["user_id"],
                        workout_id=document["workout_id"],
                        type=document["type"],
                        value=document[field],
                        unit=document["unit"],
                    ))

        return statistics if statistics else None

    def parse_xml(self) -> Generator[tuple[list[HKWorkoutCreate], list[list[HKWorkoutStatisticCreate]]], Any, None]:
        """
        Parses the XML file and yields pandas dataframes of specified chunk_size.
        Extracts attributes from each Record element.
        """
        records: list[HKRecordCreate] = []
        workouts: list[HKWorkoutCreate] = []
        statistics: list[list[HKWorkoutStatisticCreate]] = []
        
        for event, elem in ET.iterparse(self.xml_path, events=("start",)):
            if elem.tag == "Record" and event == "start":
                if len(records) >= self.chunk_size:
                    yield zip(records, [])
                    records = []
                record: dict[str, Any] = elem.attrib.copy()
                record_create = self.update_record("record", record)
                if record_create:
                    records.append(record_create)

            elif elem.tag == "Workout" and event == "start":
                if len(workouts) >= self.chunk_size:
                    yield zip(workouts, statistics)
                    workouts = []
                workout: dict[str, Any] = elem.attrib.copy()
                workout_create = self.update_record("workout", workout)
                if workout_create:
                    workouts.append(workout_create)

                # append workout statistics to workout
                for stat in elem:
                    if stat.tag != "WorkoutStatistics":
                        continue
                    statistic = stat.attrib.copy()
                    statistic["workout_id"] = workout_create.id
                    statistics_create = self.update_record("stat", statistic)
                    if statistics_create:
                        statistics.append(statistics_create)
            elem.clear()

        # yield records
        yield zip(workouts, statistics)

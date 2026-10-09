"""Read-only adapter for the Huawei tables observed in a Gadgetbridge v151 export."""

import hashlib
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from app.schemas.providers.mobile_sdk import SyncRequest

SDK_VERSION = "gadgetbridge-converter/1"
# Verified against Gadgetbridge 1d2889d2 (HuaweiSampleProvider / HuaweiWorkoutGbParser).
HUAWEI_SLEEP_STAGES = {1: "light", 2: "rem", 3: "deep", 4: "awake", 5: "sleeping"}
HUAWEI_WORKOUT_TYPES = {
    1: "running",
    2: "walking",
    3: "cycling",
    4: "hiking",
    5: "running_treadmill",
    6: "swimming_pool",
    7: "cycling_stationary",
    8: "swimming_open_water",
    13: "walking",
    14: "hiking",
}
METRICS = {
    "STEPS": ("STEP_COUNT", "count", 0, None),
    "DISTANCE": ("DISTANCE", "m", 0, None),
    "HEART_RATE": ("HEART_RATE", "bpm", 1, 300),
    "RESTING_HEART_RATE": ("RESTING_HEART_RATE", "bpm", 1, 300),
    "SPO": ("OXYGEN_SATURATION", "%", 1, 100),
}


def fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def read_rows(connection: sqlite3.Connection, table: str, required: set[str]) -> list[dict[str, Any]]:
    columns = {row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')}
    if not columns:
        return []
    if missing := required - columns:
        raise ValueError(f"Unsupported {table} schema: missing {', '.join(sorted(missing))}")
    return [dict(row) for row in connection.execute(f'SELECT * FROM "{table}"')]


class HuaweiExport:
    def __init__(
        self,
        database: Path,
        timezone_name: str = "Europe/Paris",
        device_id: int | None = None,
        gadgetbridge_user_id: int | None = None,
        hrv_kind: str | None = "rmssd",
        activity_calorie_unit: str | None = "cal",
        workout_calorie_unit: str | None = "kcal",
        sleep_stage_map: dict[int, str] | None = None,
    ) -> None:
        if hrv_kind not in (None, "rmssd", "sdnn"):
            raise ValueError("HRV must be explicitly identified as rmssd or sdnn")
        if any(unit not in (None, "cal", "kcal") for unit in (activity_calorie_unit, workout_calorie_unit)):
            raise ValueError("Calorie units must be cal or kcal")
        if sleep_stage_map and set(sleep_stage_map.values()) - {"awake", "light", "deep", "rem", "sleeping"}:
            raise ValueError("Unsupported sleep stage label")
        self.database = database
        self.tz = ZoneInfo(timezone_name)
        self.device_id = device_id
        self.user_id = gadgetbridge_user_id
        self.hrv_kind = hrv_kind
        self.activity_calorie_unit = activity_calorie_unit
        self.workout_calorie_unit = workout_calorie_unit
        self.sleep_stage_map = HUAWEI_SLEEP_STAGES if sleep_stage_map is None else sleep_stage_map
        self.report: Counter[str] = Counter()
        self.source: dict[str, str] = {}
        self.observed_users: set[int] = set()

    def timestamp(self, timestamp: int, milliseconds: bool = False) -> tuple[str, str]:
        seconds = timestamp / (1000 if milliseconds else 1)
        if not 946684800 <= seconds < 4133980800:
            raise ValueError("Timestamp outside supported epoch range; check seconds versus milliseconds")
        date = datetime.fromtimestamp(seconds, timezone.utc)
        offset = date.astimezone(self.tz).strftime("%z")
        return date.isoformat(), offset[:3] + ":" + offset[3:]

    def selected(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self.observed_users.update(
            row["USER_ID"] for row in rows if row.get("DEVICE_ID") == self.device_id and row.get("USER_ID") is not None
        )
        if self.user_id is None and len(self.observed_users) > 1:
            raise ValueError("Select --gadgetbridge-user-id for an export with multiple users")
        return [
            row
            for row in rows
            if row.get("DEVICE_ID") == self.device_id
            and (self.user_id is None or row.get("USER_ID") in (None, self.user_id))
        ]

    def metric(
        self, metric: str, value: float, unit: str, start: int, end: int, milliseconds: bool = False
    ) -> dict[str, Any]:
        start_date, offset = self.timestamp(start, milliseconds)
        end_date, _ = self.timestamp(end, milliseconds)
        identity = f"{self.source['name']}:{metric}:{start_date}"
        return {
            "id": str(uuid5(NAMESPACE_URL, identity)),
            "type": metric,
            "value": value,
            "unit": unit,
            "startDate": start_date,
            "endDate": end_date,
            "zoneOffset": offset,
            "source": self.source,
        }

    def convert(self) -> dict[str, list[dict[str, Any]]]:
        self.report.clear()
        self.observed_users.clear()
        with sqlite3.connect(self.database.resolve().as_uri() + "?mode=ro", uri=True) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only=ON")
            devices = read_rows(connection, "DEVICE", {"_id", "IDENTIFIER", "MODEL"})
            if self.device_id is None:
                if len(devices) != 1:
                    raise ValueError("Select --device-id when the export does not contain exactly one device")
                self.device_id = devices[0]["_id"]
            device = next((row for row in devices if row["_id"] == self.device_id), None)
            if device is None:
                raise ValueError("Selected device is absent from DEVICE")
            identity = hashlib.sha256(str(device["IDENTIFIER"]).encode()).hexdigest()[:16]
            self.source = {
                "name": f"Gadgetbridge:{identity}",
                "deviceModel": device.get("MODEL") or "Huawei wearable",
                "deviceType": "fitness_band",
                "appId": "nodomain.freeyourgadget.gadgetbridge",
            }
            activity = self.selected(
                read_rows(
                    connection,
                    "HUAWEI_ACTIVITY_SAMPLE",
                    {
                        "TIMESTAMP",
                        "DEVICE_ID",
                        "USER_ID",
                        "OTHER_TIMESTAMP",
                        "SOURCE",
                        "STEPS",
                        "HEART_RATE",
                        "DISTANCE",
                        "SPO",
                        "CALORIES",
                    },
                )
            )
            if self.user_id is None and len({row["USER_ID"] for row in activity}) > 1:
                raise ValueError("Select --gadgetbridge-user-id for an export with multiple users")
            self.report["activity_rows"] = len(activity)
            samples: dict[tuple[str, str], dict[str, Any]] = {}
            for row in activity:
                # Source 11 holds Huawei minute intervals; reverse boundary rows are not measurements.
                if row["SOURCE"] != 11 or row["OTHER_TIMESTAMP"] <= row["TIMESTAMP"]:
                    self.report["non_measurement_rows"] += 1
                    continue
                metrics = dict(METRICS)
                if self.activity_calorie_unit:
                    metrics["CALORIES"] = ("ACTIVE_CALORIES_BURNED", "kcal", 0, None)
                for column, (metric, unit, minimum, maximum) in metrics.items():
                    if column not in row:
                        continue
                    value = row[column]
                    # Huawei stores this sensor byte signed; -1 alone remains NOT_MEASURED.
                    if column == "HEART_RATE" and value is not None and -128 <= value < -1:
                        value &= 0xFF
                        self.report["unsigned_heart_rate_values"] += 1
                    if value is None or value < minimum or (maximum is not None and value > maximum):
                        self.report["invalid_measurements"] += 1
                        continue
                    if column == "CALORIES" and self.activity_calorie_unit == "cal":
                        value /= 1000
                    sample = self.metric(metric, value, unit, row["TIMESTAMP"], row["OTHER_TIMESTAMP"])
                    key = (metric, sample["startDate"])
                    if key in samples and samples[key]["value"] != value:
                        raise ValueError("Conflicting source/type/time measurements; refusing lossy conversion")
                    samples[key] = sample
            hrv = self.selected(
                read_rows(connection, "HUAWEI_HRV_VALUE_SAMPLE", {"TIMESTAMP", "DEVICE_ID", "LAST_TIMESTAMP", "VALUE"})
            )
            self.report["hrv_rows"] = len(hrv)
            if self.hrv_kind:
                metric = (
                    "HEART_RATE_VARIABILITY"
                    if self.hrv_kind == "rmssd"
                    else "HKQuantityTypeIdentifierHeartRateVariabilitySDNN"
                )
                for row in hrv:
                    if row["VALUE"] is None or not 0 <= row["VALUE"] <= 200:
                        self.report["invalid_measurements"] += 1
                        continue
                    sample = self.metric(metric, row["VALUE"], "ms", row["TIMESTAMP"], row["TIMESTAMP"], True)
                    samples[(metric, sample["startDate"])] = sample
            else:
                self.report["unclassified_hrv_rows"] = len(hrv)
            stages = self.selected(
                read_rows(connection, "HUAWEI_SLEEP_STAGE_SAMPLE", {"TIMESTAMP", "DEVICE_ID", "STAGE"})
            )
            windows = self.selected(
                read_rows(
                    connection, "HUAWEI_SLEEP_STATS_SAMPLE", {"DEVICE_ID", "TIMESTAMP", "BED_TIME", "WAKEUP_TIME"}
                )
            )
            sleep = self.sleep(stages, windows)
            workouts = self.selected(
                read_rows(
                    connection,
                    "HUAWEI_WORKOUT_SUMMARY_SAMPLE",
                    {
                        "WORKOUT_ID",
                        "DEVICE_ID",
                        "START_TIMESTAMP",
                        "END_TIMESTAMP",
                        "DISTANCE",
                        "STEP_COUNT",
                        "CALORIES",
                    },
                )
            )
            workout_records = self.workouts(workouts)
            for table in ["HUAWEI_STRESS_SAMPLE", "HUAWEI_TEMPERATURE_SAMPLE", "HUAWEI_EMOTIONS_SAMPLE"]:
                if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
                    self.report["unsupported_" + table.lower()] = connection.execute(
                        f'SELECT COUNT(*) FROM "{table}"'
                    ).fetchone()[0]
        data = {
            "records": sorted(samples.values(), key=lambda row: (row["startDate"], row["type"])),
            "sleep": sleep,
            "workouts": workout_records,
        }
        for collection, records in data.items():
            self.report["exported_" + collection] = len(records)
        if not any(data.values()):
            raise ValueError("No supported measurements found in the selected Huawei export")
        return data

    def sleep(self, rows: list[dict[str, Any]], windows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self.sleep_stage_map:
            self.report["unclassified_sleep_rows"] = len(rows)
            return []
        if {row["STAGE"] for row in rows} - self.sleep_stage_map.keys():
            raise ValueError("Sleep stage map does not cover every observed code")
        records = []
        for window in sorted(windows, key=lambda row: row["TIMESTAMP"]):
            selected = sorted(
                [
                    row
                    for row in rows
                    if window["TIMESTAMP"] // 60_000 * 60_000
                    <= row["TIMESTAMP"]
                    < window["WAKEUP_TIME"] // 60_000 * 60_000
                ],
                key=lambda row: row["TIMESTAMP"],
            )
            for index, row in enumerate(selected):
                end = (
                    selected[index + 1]["TIMESTAMP"]
                    if index + 1 < len(selected)
                    else window["WAKEUP_TIME"] // 60_000 * 60_000
                )
                # parseSleepDetails writes one row per minute; never invent missing minutes.
                if end > row["TIMESTAMP"] + 60_000:
                    self.report["sleep_gaps"] += 1
                end = min(end, row["TIMESTAMP"] + 60_000)
                if end <= row["TIMESTAMP"]:
                    self.report["invalid_sleep_intervals"] += 1
                    continue
                start_date, offset = self.timestamp(row["TIMESTAMP"], True)
                end_date, _ = self.timestamp(end, True)
                records.append(
                    {
                        "id": str(uuid5(NAMESPACE_URL, f"{self.source['name']}:sleep:{start_date}")),
                        "stage": self.sleep_stage_map[row["STAGE"]],
                        "startDate": start_date,
                        "endDate": end_date,
                        "zoneOffset": offset,
                        "source": self.source,
                    }
                )
        self.report["sleep_rows_outside_windows"] = len(rows) - sum(
            any(
                window["TIMESTAMP"] // 60_000 * 60_000 <= row["TIMESTAMP"] < window["WAKEUP_TIME"] // 60_000 * 60_000
                for window in windows
            )
            for row in rows
        )
        return records

    def workouts(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        records = []
        for row in rows:
            if row["END_TIMESTAMP"] <= row["START_TIMESTAMP"]:
                self.report["invalid_workouts"] += 1
                continue
            start, offset = self.timestamp(row["START_TIMESTAMP"])
            end, _ = self.timestamp(row["END_TIMESTAMP"])
            values = [
                {"type": metric, "unit": unit, "value": row[column]}
                for column, metric, unit in [("DISTANCE", "distance", "m"), ("STEP_COUNT", "stepCount", "count")]
                if row[column] is not None and row[column] >= 0
            ]
            if self.workout_calorie_unit and row["CALORIES"] is not None and row["CALORIES"] >= 0:
                energy = row["CALORIES"] / (1000 if self.workout_calorie_unit == "cal" else 1)
                values.append({"type": "activeEnergyBurned", "value": energy, "unit": "kcal"})
            code = (row.get("TYPE") or 0) & 0xFF
            if code not in HUAWEI_WORKOUT_TYPES:
                self.report["unclassified_workout_types"] += 1
            records.append(
                {
                    "id": str(uuid5(NAMESPACE_URL, f"{self.source['name']}:workout:{start}")),
                    "type": HUAWEI_WORKOUT_TYPES.get(code, "other"),
                    "startDate": start,
                    "endDate": end,
                    "zoneOffset": offset,
                    "source": self.source,
                    "values": values,
                }
            )
        return records


def batches(data: dict[str, list[dict[str, Any]]], batch_size: int = 500) -> list[dict[str, Any]]:
    if not 1 <= batch_size <= 5000:
        raise ValueError("Batch size must be between 1 and 5000")
    items = [(collection, record) for collection, records in data.items() for record in records]
    result = []
    for offset in range(0, len(items), batch_size):
        chunk: dict[str, list[dict[str, Any]]] = {"records": [], "sleep": [], "workouts": []}
        for collection, record in items[offset : offset + batch_size]:
            chunk[collection].append(record)
        latest = max(record["endDate"] for records in chunk.values() for record in records)
        raw = {
            "provider": "gadgetbridge",
            "sdkVersion": SDK_VERSION,
            "syncTimestamp": latest,
            "syncType": "historical",
            "data": chunk,
        }
        result.append(SyncRequest.model_validate(raw).model_dump(mode="json", by_alias=True))
    return result

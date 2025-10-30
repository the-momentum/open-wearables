import json
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4
from typing import Iterable
from logging import Logger, getLogger

from app.database import DbSession
from app.services.apple.healthkit.workout_service import workout_service
from app.services.apple.healthkit.workout_statistic_service import workout_statistic_service
from app.services.apple.auto_export.active_energy_service import active_energy_service
from app.services.apple.auto_export.heart_rate_service import heart_rate_service
from app.utils.exceptions import handle_exceptions
from app.schemas import (
    AEWorkoutJSON,
    AEHeartRateDataIn,
    AEHeartRateRecoveryIn,
    AEActiveEnergyIn,
    AEImportBundle,
    AERootJSON,
    HKWorkoutStatisticIn,
    HKWorkoutStatisticCreate,
    HKWorkoutCreate,
    HKWorkoutIn,
    AEHeartRateDataCreate,
    AEHeartRateRecoveryCreate,
    AEActiveEnergyCreate,
    UploadDataResponse,
)


APPLE_DT_FORMAT = "%Y-%m-%d %H:%M:%S %z"

class ImportService:
    def __init__(self, log: Logger, **kwargs):
        self.log = log
        self.workout_service = workout_service
        self.workout_statistic_service = workout_statistic_service
        self.active_energy_service = active_energy_service
        self.heart_rate_data_service = heart_rate_service.heart_rate_data_service
        self.heart_rate_recovery_service = heart_rate_service.heart_rate_recovery_service

    def _dt(self, s: str) -> datetime:
        s = s.replace(" +", "+").replace(" ", "T", 1)
        if len(s) >= 5 and (s[-5] in {"+", "-"} and s[-3] != ":"):
            s = f"{s[:-2]}:{s[-2:]}"
        return datetime.fromisoformat(s)

    def _dec(self, x: float | int | None) -> Decimal | None:
        return None if x is None else Decimal(str(x))


    def _get_workout_statistics(self, workout: AEWorkoutJSON) -> list[HKWorkoutStatisticIn]:
        """
        Get workout statistics from workout JSON.
        """
        statistics: list[HKWorkoutStatisticIn] = []
        
        if workout.activeEnergyBurned is not None:
            ae_data = workout.activeEnergyBurned
            statistics.append(HKWorkoutStatisticIn(
                type="totalEnergyBurned",
                value=ae_data.qty or 0,
                unit=ae_data.units or 'kcal'
            ))
        
        if workout.distance is not None:
            dist_data = workout.distance
            statistics.append(HKWorkoutStatisticIn(
                type="totalDistance",
                value=dist_data.qty or 0,
                unit=dist_data.units or 'm'
            ))
        
        if workout.intensity is not None:
            intensity_data = workout.intensity
            statistics.append(HKWorkoutStatisticIn(
                type="averageIntensity",
                value=intensity_data.qty or 0,
                unit=intensity_data.units or 'kcal/hr·kg'
            ))
        
        if workout.temperature is not None:
            temp_data = workout.temperature
            statistics.append(HKWorkoutStatisticIn(
                type="environmentalTemperature",
                value=temp_data.qty or 0,
                unit=temp_data.units or 'degC'
            ))
        
        if workout.humidity is not None:
            humidity_data = workout.humidity
            statistics.append(HKWorkoutStatisticIn(
                type="environmentalHumidity",
                value=humidity_data.qty or 0,
                unit=humidity_data.units or '%'
            ))

        return statistics

    def _get_records(self, workout: AEWorkoutJSON, wid: UUID) -> tuple[list[AEHeartRateDataIn], list[AEHeartRateRecoveryIn], list[AEActiveEnergyIn]]:
        hr_data_rows: list[AEHeartRateDataIn] = []
        for e in workout.heartRateData or []:
            hr_data_rows.append(
                AEHeartRateDataIn(
                    workout_id=wid,
                    date=self._dt(e.date),
                    source=e.source,
                    units=e.units,
                    avg=self._dec(e.avg),
                    min=self._dec(e.min),
                    max=self._dec(e.max),
                )
            )

        hr_recovery_rows: list[AEHeartRateRecoveryIn] = []
        for e in workout.heartRateRecovery or []:
            hr_recovery_rows.append(
                AEHeartRateRecoveryIn(
                    workout_id=wid,
                    date=self._dt(e.date),
                    source=e.source,
                    units=e.units,
                    avg=self._dec(e.avg),
                    min=self._dec(e.min),
                    max=self._dec(e.max),
                )
            )

        ae_rows: list[AEActiveEnergyIn] = []
        for e in workout.activeEnergy or []:
            ae_rows.append(
                AEActiveEnergyIn(
                    workout_id=wid,
                    date=self._dt(e.date),
                    source=e.source,
                    units=e.units,
                    qty=self._dec(e.qty),
                )
            )
        
        return hr_data_rows, hr_recovery_rows, ae_rows

    def _build_import_bundles(self, raw: dict) -> Iterable[AEImportBundle]:
        """
        Given the parsed JSON dict from HealthAutoExport, yield ImportBundles
        ready to insert the database.
        """
        root = AERootJSON(**raw)
        workouts_raw = root.data.get("workouts", [])
        
        for w in workouts_raw:
            wjson = AEWorkoutJSON(**w)

            wid = uuid4()

            start_date = self._dt(wjson.start)
            end_date = self._dt(wjson.end)
            duration = (end_date - start_date).total_seconds() / 60
            duration_unit = "min"

            workout_statistics = self._get_workout_statistics(wjson)

            workout_type = wjson.name or 'Unknown Workout'

            workout_row = HKWorkoutIn(
                id=wid,
                type=workout_type,
                startDate=start_date,
                endDate=end_date,
                duration=self._dec(duration),
                durationUnit=duration_unit,
                sourceName="Auto Export",
                workoutStatistics=None
            )

            heart_rate_data, heart_rate_recovery, active_energy = self._get_records(wjson, wid)

            yield AEImportBundle(
                workout=workout_row,
                workout_statistics=workout_statistics,
                heart_rate_data=heart_rate_data,
                heart_rate_recovery=heart_rate_recovery,
                active_energy=active_energy
            )


    def load_data(self, db_session: DbSession, raw: dict, user_id: str = None) -> bool:

        for bundle in self._build_import_bundles(raw):

            workout_dict = bundle.workout.model_dump()
            
            if user_id:
                workout_dict['user_id'] = UUID(user_id)
            
            workout_create = HKWorkoutCreate(**workout_dict)
            created_workout = self.workout_service.create(db_session, workout_create)

            for stat in bundle.workout_statistics:
                stat_dict = stat.model_dump()
                if user_id:
                    stat_dict['user_id'] = UUID(user_id)
                    stat_dict['workout_id'] = created_workout.id
                stat_create = HKWorkoutStatisticCreate(**stat_dict)
                self.workout_statistic_service.create(db_session, stat_create)

            for row in bundle.heart_rate_data:
                hr_data = row.model_dump()
                if user_id:
                    hr_data['user_id'] = UUID(user_id)
                hr_create = AEHeartRateDataCreate(**hr_data)
                self.heart_rate_data_service.create(db_session, hr_create)

            for row in bundle.heart_rate_recovery:
                hr_recovery_data = row.model_dump()
                if user_id:
                    hr_recovery_data['user_id'] = UUID(user_id)
                hr_recovery_create = AEHeartRateRecoveryCreate(**hr_recovery_data)
                self.heart_rate_recovery_service.create(db_session, hr_recovery_create)

            for row in bundle.active_energy:
                ae_data = row.model_dump()
                if user_id:
                    ae_data['user_id'] = UUID(user_id)
                ae_create = AEActiveEnergyCreate(**ae_data)
                self.active_energy_service.create(db_session, ae_create)

        return True


    @handle_exceptions
    async def import_data_from_request(
        self, 
        db_session: DbSession,
        request_content: str, 
        content_type: str,
        user_id: str
    ) -> UploadDataResponse:
        try:
            # Parse content based on type
            if "multipart/form-data" in content_type:
                data = self._parse_multipart_content(request_content)
            else:
                data = self._parse_json_content(request_content)
            
            if not data:
                return UploadDataResponse(status_code=400, response="No valid data found")
            
            # Load data using provided database session
            self.load_data(db_session, data, user_id=user_id)
                
        except Exception as e:
            return UploadDataResponse(status_code=400, response=f"Import failed: {str(e)}")

        return UploadDataResponse(status_code=200, response="Import successful")


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
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    json_end = i
                    break
        
        if brace_count != 0:
            return None
            
        json_str = content[json_start:json_end + 1]
        return json.loads(json_str)


    def _parse_json_content(self, content: str) -> dict | None:
        """Parse JSON content directly."""
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return None


import_service = ImportService(log=getLogger(__name__))

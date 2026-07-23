"""Google Health API sleep handler.

Fetches Sleep sessions via the dataPoints ``list`` operation and stores them as
``EventRecord(category="sleep")`` via ``create_or_merge_sleep`` (merges fragmented
sessions). Composed into GoogleHealth247Data.load_and_save_all.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.config import settings
from app.constants.google_health_endpoints import LIST_ENDPOINT as DATAPOINTS_LIST_ENDPOINT
from app.constants.series_types.google.sleep_stages import GOOGLE_SLEEP_STAGE_MAP
from app.constants.sleep import SleepStageType
from app.database import DbSession
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas.enums import ProviderName
from app.schemas.model_crud.activities import EventRecordCreate, EventRecordDetailCreate
from app.schemas.model_crud.activities.sleep import SleepStage
from app.services.event_record_service import event_record_service
from app.services.providers.api_client import make_authenticated_request
from app.services.providers.google.health_api.helpers import (
    GOOGLE_HEALTH_API_SOURCE,
    extract_source,
    parse_interval,
    parse_rfc3339,
    physical_interval,
    read_number,
    zone_offset_from,
)
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.raw_payload_storage import store_raw_payload
from app.utils.conversion import as_int, to_decimal


class GoogleHealthApiSleep:
    """Fetches Google Health API Sleep sessions and stores them as sleep EventRecords."""

    LIST_ENDPOINT = DATAPOINTS_LIST_ENDPOINT.format(data_type="sleep")
    PAGE_SIZE = 1000

    def __init__(self, oauth: BaseOAuthTemplate, connection_repo: UserConnectionRepository, api_base_url: str):
        self.oauth = oauth
        self.connection_repo = connection_repo
        self.provider_name = "google"
        self.api_base_url = api_base_url
        self.logger = logging.getLogger(self.__class__.__name__)

    def load_and_save(self, db: DbSession, user_id: UUID, start_time: datetime, end_time: datetime) -> int:
        """Fetch sleep sessions starting in the window and merge-save each."""
        count = 0
        for point in self._fetch(db, user_id, start_time, end_time):
            sleep = point.get("sleep")
            if not isinstance(sleep, dict):
                continue
            interval = sleep.get("interval") or {}
            start, end = parse_interval(interval)
            if start is None or end is None or not (start_time <= start < end_time):
                continue
            record, detail = self._normalize(point, sleep, interval, start, end, user_id)
            event_record_service.create_or_merge_sleep(db, user_id, record, detail, settings.sleep_end_gap_minutes)
            count += 1
        return count

    def _fetch(self, db: DbSession, user_id: UUID, start_time: datetime, end_time: datetime) -> list[dict[str, Any]]:
        window_start = physical_interval(start_time, end_time)["startTime"]
        time_filter = f'sleep.interval.end_time >= "{window_start}"'
        points: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {"pageSize": self.PAGE_SIZE, "filter": time_filter}
            if page_token:
                params["pageToken"] = page_token
            response = make_authenticated_request(
                db=db,
                user_id=user_id,
                connection_repo=self.connection_repo,
                oauth=self.oauth,
                api_base_url=self.api_base_url,
                provider_name=self.provider_name,
                endpoint=self.LIST_ENDPOINT,
                method="GET",
                params=params,
            )
            store_raw_payload(
                source="api_response",
                provider=self.provider_name,
                payload=response,
                user_id=str(user_id),
                trace_id=self.LIST_ENDPOINT,
            )
            if not isinstance(response, dict):
                break
            points.extend(response.get("dataPoints", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break
        return points

    def _normalize(
        self,
        point: dict[str, Any],
        sleep: dict[str, Any],
        interval: dict[str, Any],
        start: datetime,
        end: datetime,
        user_id: UUID,
    ) -> tuple[EventRecordCreate, EventRecordDetailCreate]:
        record_id = uuid4()
        source_name, device_model = extract_source(point.get("dataSource"))
        zone_offset = zone_offset_from(interval.get("startUtcOffset"))
        metadata = sleep.get("metadata") or {}

        record = EventRecordCreate(
            id=record_id,
            category="sleep",
            provider=ProviderName.GOOGLE.value,
            source=GOOGLE_HEALTH_API_SOURCE,
            source_name=source_name,
            device_model=device_model,
            external_id=point.get("name") or metadata.get("externalId"),
            start_datetime=start,
            end_datetime=end,
            duration_seconds=int((end - start).total_seconds()),
            zone_offset=zone_offset,
            user_id=user_id,
        )
        return record, self._build_detail(record_id, sleep, metadata)

    def _build_detail(
        self,
        record_id: UUID,
        sleep: dict[str, Any],
        metadata: dict[str, Any],
    ) -> EventRecordDetailCreate:
        summary = sleep.get("summary") or {}
        stage_minutes = {
            s.get("type"): to_decimal(s.get("minutes")) for s in summary.get("stagesSummary", []) if isinstance(s, dict)
        }
        in_bed = read_number(summary, "minutesInSleepPeriod")
        asleep = read_number(summary, "minutesAsleep")
        efficiency = (asleep / in_bed * 100).quantize(Decimal("0.1")) if asleep is not None and in_bed else None
        awake = stage_minutes.get("AWAKE")
        if awake is None:
            awake = read_number(summary, "minutesAwake")

        return EventRecordDetailCreate(
            record_id=record_id,
            sleep_time_in_bed_minutes=as_int(in_bed),
            sleep_total_duration_minutes=as_int(asleep),
            sleep_awake_minutes=as_int(awake),
            sleep_deep_minutes=as_int(stage_minutes.get("DEEP")),
            sleep_rem_minutes=as_int(stage_minutes.get("REM")),
            sleep_light_minutes=as_int(stage_minutes.get("LIGHT")),
            sleep_efficiency_score=efficiency,
            is_nap=metadata.get("nap"),
            sleep_stages=self._build_stages(sleep.get("stages", [])) or None,
        )

    @staticmethod
    def _build_stages(stages: list[dict[str, Any]]) -> list[SleepStage]:
        result: list[SleepStage] = []
        for stage in stages:
            start = parse_rfc3339(stage.get("startTime"))
            end = parse_rfc3339(stage.get("endTime"))
            if start is None or end is None:
                continue
            result.append(
                SleepStage(
                    stage=GOOGLE_SLEEP_STAGE_MAP.get(stage.get("type", ""), SleepStageType.UNKNOWN),
                    start_time=start,
                    end_time=end,
                )
            )
        return result

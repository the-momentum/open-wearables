"""The SDK's metric record: the count HealthKit reports for a sample."""

from typing import Any

from app.schemas.providers.mobile_sdk.sync_request import MetricRecord

_RECORD: dict[str, Any] = {
    "type": "HKQuantityTypeIdentifierActiveEnergyBurned",
    "startDate": "2026-07-02T20:27:00Z",
    "endDate": "2026-07-02T20:37:00Z",
    "value": 15,
    "unit": "kcal",
}


class TestMetricRecordCount:
    def test_count_is_read_when_the_sdk_sends_it(self) -> None:
        assert MetricRecord.model_validate({**_RECORD, "count": 10}).count == 10

    def test_count_is_none_from_an_sdk_that_does_not_send_it(self) -> None:
        assert MetricRecord.model_validate(_RECORD).count is None

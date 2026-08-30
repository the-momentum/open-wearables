from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.schemas.enums import SeriesType
from app.services.providers.whoop.data_247 import Whoop247Data


@pytest.fixture
def data_247() -> Whoop247Data:
    return Whoop247Data(provider_name="whoop", api_base_url="https://example.com", oauth=Mock())


def test_normalize_sleep_exposes_whoop_sleep_details(data_247: Whoop247Data) -> None:
    raw = {
        "id": str(uuid4()),
        "start": "2026-08-29T22:00:00Z",
        "end": "2026-08-30T06:00:00Z",
        "score_state": "SCORED",
        "score": {
            "sleep_performance_percentage": 94,
            "sleep_consistency_percentage": 83,
            "sleep_efficiency_percentage": 96.12,
            "respiratory_rate": 18.67,
            "stage_summary": {
                "total_in_bed_time_milli": 28_800_000,
                "sleep_cycle_count": 9,
                "disturbance_count": 7,
                "total_no_data_time_milli": 180_000,
            },
            "sleep_needed": {
                "baseline_milli": 27_000_000,
                "need_from_sleep_debt_milli": 1_800_000,
                "need_from_recent_strain_milli": 900_000,
                "need_from_recent_nap_milli": -600_000,
            },
        },
    }

    normalized, score = data_247.normalize_sleep(raw, uuid4())

    assert normalized["sleep_cycle_count"] == 9
    assert normalized["disturbance_count"] == 7
    assert normalized["total_no_data_minutes"] == 3
    assert normalized["sleep_need_baseline_minutes"] == 450
    assert normalized["sleep_need_from_debt_minutes"] == 30
    assert normalized["sleep_need_from_recent_strain_minutes"] == 15
    assert normalized["sleep_need_from_recent_nap_minutes"] == -10
    assert score is not None
    assert score.components is not None
    assert score.components["sleep_cycle_count"].value == 9
    assert score.components["disturbance_count"].value == 7
    assert score.components["sleep_need_from_debt_minutes"].value == 30


def test_normalize_sleep_omits_missing_optional_details(data_247: Whoop247Data) -> None:
    raw = {
        "start": "2026-08-29T22:00:00Z",
        "end": "2026-08-30T06:00:00Z",
        "score_state": "SCORED",
        "score": {"sleep_performance_percentage": 80},
    }

    _, score = data_247.normalize_sleep(raw, uuid4())

    assert score is not None
    assert score.components is None


def test_body_measurement_preserves_max_heart_rate(data_247: Whoop247Data, monkeypatch: pytest.MonkeyPatch) -> None:
    db = Mock()
    monkeypatch.setattr(
        data_247,
        "get_body_measurement",
        Mock(return_value={"height_meter": 1.55, "weight_kilogram": 54.35, "max_heart_rate": 186}),
    )
    monkeypatch.setattr(data_247, "_get_latest_value", Mock(return_value=None))
    bulk_create = Mock(return_value=3)
    monkeypatch.setattr("app.services.providers.whoop.data_247.timeseries_service.bulk_create_samples", bulk_create)

    assert data_247.load_and_save_body_measurement(db, uuid4()) == 3

    samples = bulk_create.call_args.args[1]
    by_type = {sample.series_type: float(sample.value) for sample in samples}
    assert by_type == {SeriesType.height: 155, SeriesType.weight: 54.35, SeriesType.max_heart_rate: 186}
    db.commit.assert_called_once()

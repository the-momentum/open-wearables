"""Guard: retired series names keep working until the 1.0 cut."""

import pytest

from app.constants.webhooks.events import SERIES_TYPE_TO_GRANULAR_EVENT, SERIES_TYPE_TO_GROUP_EVENT
from app.schemas.enums import SeriesType, get_series_type_id


class TestRetiredSeriesTypeNames:
    def test_retired_name_resolves_to_the_current_member(self) -> None:
        assert SeriesType("energy") is SeriesType.active_energy
        assert SeriesType("active_energy") is SeriesType.active_energy

    @pytest.mark.parametrize(
        ("retired", "current"),
        [
            ("energy", SeriesType.active_energy),
            ("walking_heart_rate_average", SeriesType.walking_heart_rate),
            ("average_met", SeriesType.physical_effort),
        ],
    )
    def test_every_retired_name_resolves_and_answers_with_the_current_one(
        self, retired: str, current: SeriesType
    ) -> None:
        assert SeriesType(retired) is current
        assert SeriesType(retired).value == current.value

    def test_both_spellings_share_the_stored_id(self) -> None:
        """The id is what rows reference, so the rename must not move it."""
        assert get_series_type_id(SeriesType("energy")) == 81
        assert get_series_type_id(SeriesType("walking_heart_rate_average")) == 5

    def test_responses_carry_the_current_name(self) -> None:
        """The alias is lookup-only; nothing should serialize the retired spelling back."""
        assert SeriesType("energy").value == "active_energy"

    def test_unknown_names_are_still_rejected(self) -> None:
        with pytest.raises(ValueError, match="not a valid SeriesType"):
            SeriesType("not_a_series_type")

    def test_webhook_maps_are_keyed_by_the_current_name(self) -> None:
        """A missing key makes the emitter return without firing, so this fails silently."""
        for mapping in (SERIES_TYPE_TO_GROUP_EVENT, SERIES_TYPE_TO_GRANULAR_EVENT):
            assert {"active_energy", "walking_heart_rate", "physical_effort"} <= set(mapping)
            assert not {"energy", "walking_heart_rate_average", "average_met"} & set(mapping)

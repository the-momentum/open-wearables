"""
Regression tests for XMLService (xml_service.py).

Covers:
- Steps records land under SeriesType.steps (not heart_rate or any other type)
- Heart rate records land under SeriesType.heart_rate (not steps)
- Unsupported HK category types increment the skip counter (Bug B regression)
- Parse stats balance: read == processed + skipped for every run
"""

import textwrap
from pathlib import Path

import pytest

from app.schemas.enums import SeriesType
from app.schemas.model_crud.activities import HeartRateSampleCreate, StepSampleCreate
from app.schemas.providers.apple.apple_xml.stats import XMLParseStats
from app.services.apple.apple_xml.xml_service import XMLService


# A minimal but complete Apple Health XML fixture:
#  - 2 heart_rate records
#  - 3 step_count records
#  - 1 resting_heart_rate record
#  - 2 unsupported category-type records (AppleStandHour, MindfulSession)
#  - 1 heart_rate record with an invalid decimal value
FIXTURE_XML = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <HealthData locale="en_US">
      <Record type="HKQuantityTypeIdentifierHeartRate"
        sourceName="Apple Watch" unit="count/min"
        startDate="2026-01-01 08:00:00 +0000"
        endDate="2026-01-01 08:00:05 +0000" value="72"/>
      <Record type="HKQuantityTypeIdentifierHeartRate"
        sourceName="Apple Watch" unit="count/min"
        startDate="2026-01-01 08:01:00 +0000"
        endDate="2026-01-01 08:01:05 +0000" value="75"/>
      <Record type="HKQuantityTypeIdentifierStepCount"
        sourceName="iPhone" unit="count"
        startDate="2026-01-01 08:00:00 +0000"
        endDate="2026-01-01 08:05:00 +0000" value="120"/>
      <Record type="HKQuantityTypeIdentifierStepCount"
        sourceName="iPhone" unit="count"
        startDate="2026-01-01 09:00:00 +0000"
        endDate="2026-01-01 09:05:00 +0000" value="200"/>
      <Record type="HKQuantityTypeIdentifierStepCount"
        sourceName="iPhone" unit="count"
        startDate="2026-01-01 10:00:00 +0000"
        endDate="2026-01-01 10:05:00 +0000" value="150"/>
      <Record type="HKQuantityTypeIdentifierRestingHeartRate"
        sourceName="Apple Watch" unit="count/min"
        startDate="2026-01-01 07:00:00 +0000"
        endDate="2026-01-01 07:00:01 +0000" value="58"/>
      <Record type="HKCategoryTypeIdentifierAppleStandHour"
        sourceName="Apple Watch" unit=""
        startDate="2026-01-01 09:00:00 +0000"
        endDate="2026-01-01 10:00:00 +0000" value="1"/>
      <Record type="HKCategoryTypeIdentifierMindfulSession"
        sourceName="iPhone" unit=""
        startDate="2026-01-01 10:00:00 +0000"
        endDate="2026-01-01 10:10:00 +0000" value="1"/>
      <Record type="HKQuantityTypeIdentifierHeartRate"
        sourceName="Apple Watch" unit="count/min"
        startDate="2026-01-01 08:30:00 +0000"
        endDate="2026-01-01 08:30:05 +0000" value="INVALID"/>
    </HealthData>
""")

USER_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture()
def fixture_xml(tmp_path: Path) -> Path:
    xml_file = tmp_path / "test_export.xml"
    xml_file.write_text(FIXTURE_XML, encoding="utf-8")
    return xml_file


@pytest.fixture()
def parsed_output(fixture_xml: Path, caplog: pytest.LogCaptureFixture):
    import logging

    service = XMLService(fixture_xml, logging.getLogger("test_xml_service"))
    all_records = []
    all_workouts = []
    for ts_records, workouts, _ in service.parse_xml(USER_ID):
        all_records.extend(ts_records)
        all_workouts.extend(workouts)
    return all_records, all_workouts, service.stats


class TestXMLServiceTypeAttribution:
    """Steps and HR records must land under their own series types, not each other's."""

    def test_steps_land_as_steps(self, parsed_output):
        records, _, _ = parsed_output
        step_records = [r for r in records if r.series_type == SeriesType.steps]
        assert len(step_records) == 3, (
            f"Expected 3 step records, got {len(step_records)}; "
            f"types seen: {[r.series_type for r in records]}"
        )

    def test_steps_are_StepSampleCreate_instances(self, parsed_output):
        records, _, _ = parsed_output
        step_records = [r for r in records if r.series_type == SeriesType.steps]
        for r in step_records:
            assert isinstance(r, StepSampleCreate), (
                f"Step record is {type(r).__name__}, expected StepSampleCreate"
            )

    def test_heart_rate_lands_as_heart_rate(self, parsed_output):
        records, _, _ = parsed_output
        hr_records = [r for r in records if r.series_type == SeriesType.heart_rate]
        # 2 valid HR records; 1 INVALID-value HR is skipped
        assert len(hr_records) == 2, (
            f"Expected 2 heart_rate records, got {len(hr_records)}; "
            f"types seen: {[r.series_type for r in records]}"
        )

    def test_heart_rate_are_HeartRateSampleCreate_instances(self, parsed_output):
        records, _, _ = parsed_output
        hr_records = [r for r in records if r.series_type == SeriesType.heart_rate]
        for r in hr_records:
            assert isinstance(r, HeartRateSampleCreate), (
                f"HR record is {type(r).__name__}, expected HeartRateSampleCreate"
            )

    def test_no_steps_in_heart_rate_bucket(self, parsed_output):
        records, _, _ = parsed_output
        hr_records = [r for r in records if r.series_type == SeriesType.heart_rate]
        step_values = {120, 200, 150}
        for r in hr_records:
            assert float(r.value) not in step_values, (
                f"Step value {r.value} found in heart_rate bucket — type misattribution!"
            )

    def test_no_heart_rate_in_steps_bucket(self, parsed_output):
        records, _, _ = parsed_output
        step_records = [r for r in records if r.series_type == SeriesType.steps]
        hr_values = {72, 75}
        for r in step_records:
            assert float(r.value) not in hr_values, (
                f"Heart rate value {r.value} found in steps bucket — type misattribution!"
            )


class TestXMLServiceSkipCounter:
    """Every non-landed record must appear in the skip counter with a reason (Bug B regression)."""

    def test_unsupported_types_increment_skip_counter(self, parsed_output):
        _, _, stats = parsed_output
        # 2 unsupported category records + 1 invalid-value HR = 3 skips total
        assert stats.records.skipped == 3, (
            f"Expected 3 skipped records, got {stats.records.skipped}. "
            "Unsupported-type records may be silently dropped (Bug B)."
        )

    def test_unsupported_type_reason_is_named(self, parsed_output):
        _, _, stats = parsed_output
        reasons = stats.records.reasons
        unsupported_reasons = [r for r in reasons if r.startswith("unsupported_type:")]
        assert len(unsupported_reasons) >= 1, (
            f"No 'unsupported_type:*' reason in skip counter; got: {dict(reasons)}"
        )

    def test_invalid_value_reason_is_named(self, parsed_output):
        _, _, stats = parsed_output
        reasons = stats.records.reasons
        invalid_reasons = [r for r in reasons if r.startswith("invalid_value:")]
        assert len(invalid_reasons) >= 1, (
            f"No 'invalid_value:*' reason in skip counter; got: {dict(reasons)}"
        )

    def test_skip_counter_balance_read_equals_processed_plus_skipped(self, parsed_output):
        _, _, stats = parsed_output
        assert stats.records.is_balanced(), (
            f"Balance fail: read={stats.records.read}, "
            f"processed={stats.records.processed}, "
            f"skipped={stats.records.skipped}. "
            f"read != processed + skipped — silent drops remain."
        )

    def test_malformed_record_increments_skip_counter(self, tmp_path: Path):
        """Feeding one unmappable record confirms the skip counter increments (7.3c)."""
        import logging

        xml_content = textwrap.dedent("""\
            <?xml version="1.0" encoding="UTF-8"?>
            <HealthData locale="en_US">
              <Record type="HKCategoryTypeIdentifierAppleStandHour"
                sourceName="Apple Watch" unit=""
                startDate="2026-01-01 09:00:00 +0000"
                endDate="2026-01-01 10:00:00 +0000" value="1"/>
            </HealthData>
        """)
        xml_file = tmp_path / "malformed.xml"
        xml_file.write_text(xml_content, encoding="utf-8")

        service = XMLService(xml_file, logging.getLogger("test_malformed"))
        for _ in service.parse_xml(USER_ID):
            pass

        assert service.stats.records.skipped == 1, (
            "One unsupported-type record must increment skip counter to 1; "
            f"got {service.stats.records.skipped}. Bug B is not fixed."
        )
        reasons = service.stats.records.reasons
        assert any(r.startswith("unsupported_type:") for r in reasons), (
            f"No 'unsupported_type:*' reason in skip counter; got: {dict(reasons)}"
        )


# --- ActivitySummary tests ---

ACTIVITY_SUMMARY_XML = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <HealthData locale="en_US">
      <ActivitySummary dateComponents="2026-08-13"
        activeEnergyBurned="90.96" activeEnergyBurnedGoal="740"
        activeEnergyBurnedUnit="Cal"
        appleMoveTime="0" appleMoveTimeGoal="0"
        appleExerciseTime="2" appleExerciseTimeGoal="30"
        appleStandHours="7" appleStandHoursGoal="12"/>
      <ActivitySummary dateComponents="2026-08-12"
        activeEnergyBurned="0" activeEnergyBurnedGoal="740"
        activeEnergyBurnedUnit="Cal"
        appleMoveTime="0" appleMoveTimeGoal="0"
        appleExerciseTime="0" appleExerciseTimeGoal="30"
        appleStandHours="0" appleStandHoursGoal="12"/>
    </HealthData>
""")

ACTIVITY_SUMMARY_PARTIAL_XML = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <HealthData locale="en_US">
      <ActivitySummary dateComponents="2026-08-13"
        activeEnergyBurned="90.96" activeEnergyBurnedGoal="740"
        activeEnergyBurnedUnit="Cal"
        appleExerciseTime="2" appleExerciseTimeGoal="30"
        appleStandHours="7" appleStandHoursGoal="12"/>
    </HealthData>
""")

ACTIVITY_SUMMARY_DUPLICATE_XML = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <HealthData locale="en_US">
      <ActivitySummary dateComponents="2026-08-13"
        activeEnergyBurned="90.96" activeEnergyBurnedGoal="740"
        activeEnergyBurnedUnit="Cal"
        appleMoveTime="0" appleMoveTimeGoal="0"
        appleExerciseTime="2" appleExerciseTimeGoal="30"
        appleStandHours="7" appleStandHoursGoal="12"/>
      <ActivitySummary dateComponents="2026-08-13"
        activeEnergyBurned="100" activeEnergyBurnedGoal="740"
        activeEnergyBurnedUnit="Cal"
        appleMoveTime="5" appleMoveTimeGoal="0"
        appleExerciseTime="10" appleExerciseTimeGoal="30"
        appleStandHours="9" appleStandHoursGoal="12"/>
    </HealthData>
""")


class TestActivitySummaryParsing:
    """ActivitySummary elements must be parsed and counted correctly."""

    def test_full_attribute_element_parsed(self, tmp_path: Path):
        import logging
        from decimal import Decimal

        xml_file = tmp_path / "activity.xml"
        xml_file.write_text(ACTIVITY_SUMMARY_XML, encoding="utf-8")
        service = XMLService(xml_file, logging.getLogger("test_activity"))
        for _ in service.parse_xml(USER_ID):
            pass

        assert len(service.activity_summaries) == 2
        s = service.activity_summaries[0]
        assert str(s["date"]) == "2026-08-13"
        assert s["active_energy_burned"] == Decimal("90.96")
        assert s["active_energy_burned_goal"] == Decimal("740")
        assert s["active_energy_burned_unit"] == "Cal"
        assert s["apple_exercise_time"] == Decimal("2")
        assert s["apple_exercise_time_goal"] == Decimal("30")
        assert s["apple_stand_hours"] == Decimal("7")
        assert s["apple_stand_hours_goal"] == Decimal("12")

    def test_missing_optional_attributes_default_to_zero(self, tmp_path: Path):
        """Elements missing appleMoveTime/Goal still parse — defaults to 0."""
        import logging
        from decimal import Decimal

        xml_file = tmp_path / "activity_partial.xml"
        xml_file.write_text(ACTIVITY_SUMMARY_PARTIAL_XML, encoding="utf-8")
        service = XMLService(xml_file, logging.getLogger("test_activity_partial"))
        for _ in service.parse_xml(USER_ID):
            pass

        assert len(service.activity_summaries) == 1
        s = service.activity_summaries[0]
        assert s["apple_move_time"] == Decimal("0")
        assert s["apple_move_time_goal"] == Decimal("0")

    def test_duplicate_dates_both_accumulated(self, tmp_path: Path):
        """Same date appearing twice: both are accumulated (dedup at DB layer)."""
        import logging

        xml_file = tmp_path / "activity_dup.xml"
        xml_file.write_text(ACTIVITY_SUMMARY_DUPLICATE_XML, encoding="utf-8")
        service = XMLService(xml_file, logging.getLogger("test_activity_dup"))
        for _ in service.parse_xml(USER_ID):
            pass

        assert len(service.activity_summaries) == 2
        assert service.stats.activity_summaries.read == 2
        assert service.stats.activity_summaries.processed == 2
        assert service.stats.activity_summaries.skipped == 0

    def test_balance_holds(self, tmp_path: Path):
        """read == processed + skipped for activity_summaries."""
        import logging

        xml_file = tmp_path / "activity.xml"
        xml_file.write_text(ACTIVITY_SUMMARY_XML, encoding="utf-8")
        service = XMLService(xml_file, logging.getLogger("test_balance"))
        for _ in service.parse_xml(USER_ID):
            pass

        assert service.stats.activity_summaries.is_balanced()
        assert service.stats.activity_summaries.read == 2
        assert service.stats.activity_summaries.processed == 2

    def test_existing_record_and_sleep_counters_unaffected(self, tmp_path: Path):
        """Adding ActivitySummary must not disturb Record/Sleep counters."""
        import logging

        # XML with both Records and ActivitySummary
        mixed_xml = textwrap.dedent("""\
            <?xml version="1.0" encoding="UTF-8"?>
            <HealthData locale="en_US">
              <Record type="HKQuantityTypeIdentifierStepCount"
                sourceName="iPhone" unit="count"
                startDate="2026-01-01 08:00:00 +0000"
                endDate="2026-01-01 08:05:00 +0000" value="120"/>
              <ActivitySummary dateComponents="2026-08-13"
                activeEnergyBurned="90.96" activeEnergyBurnedGoal="740"
                activeEnergyBurnedUnit="Cal"
                appleMoveTime="0" appleMoveTimeGoal="0"
                appleExerciseTime="2" appleExerciseTimeGoal="30"
                appleStandHours="7" appleStandHoursGoal="12"/>
            </HealthData>
        """)
        xml_file = tmp_path / "mixed.xml"
        xml_file.write_text(mixed_xml, encoding="utf-8")
        service = XMLService(xml_file, logging.getLogger("test_mixed"))
        all_records = []
        for ts_records, _, _ in service.parse_xml(USER_ID):
            all_records.extend(ts_records)

        # Record counters unchanged
        assert service.stats.records.read == 1
        assert service.stats.records.processed == 1
        assert service.stats.records.is_balanced()
        assert len(all_records) == 1

        # ActivitySummary counted separately
        assert service.stats.activity_summaries.read == 1
        assert service.stats.activity_summaries.processed == 1
        assert len(service.activity_summaries) == 1

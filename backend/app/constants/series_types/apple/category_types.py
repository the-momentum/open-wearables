from enum import StrEnum


class AppleCategoryType(StrEnum):
    """
    Apple HealthKit category type identifiers (HKCategoryTypeIdentifier...).

    These represent categorical health data like sleep analysis.
    """

    SLEEP_ANALYSIS = "HKCategoryTypeIdentifierSleepAnalysis"


# Category types set (for backwards compatibility and validation)
CATEGORY_TYPE_IDENTIFIERS: set[AppleCategoryType] = {
    AppleCategoryType.SLEEP_ANALYSIS,
}

from enum import StrEnum

from app.schemas.series_types import SeriesType


class AppleCategoryType(StrEnum):
    """
    Apple HealthKit category type identifiers (HKCategoryTypeIdentifier...).

    These represent categorical health data like sleep analysis.
    """

    SLEEP_ANALYSIS = "HKCategoryTypeIdentifierSleepAnalysis"

    """
    EVENTS
    Values: 0 = nonApplicable, 1 = depends on event type
    """
    HANDWASHING_EVENT = "HKCategoryTypeIdentifierHandwashingEvent"
    TOOTHBRUSHING_EVENT = "HKCategoryTypeIdentifierToothbrushingEvent"
    HIGH_HEART_RATE_EVENT = "HKCategoryTypeIdentifierHighHeartRateEvent"
    LOW_HEART_RATE_EVENT = "HKCategoryTypeIdentifierLowHeartRateEvent"
    IRREGULAR_HEART_RHYTHM_EVENT = "HKCategoryTypeIdentifierIrregularHeartRhythmEvent"
    APPLE_WALKING_STEADINESS_EVENT = "HKCategoryTypeIdentifierAppleWalkingSteadinessEvent"
    LOW_CARDIO_FITNESS_EVENT = "HKCategoryTypeIdentifierLowCardioFitnessEvent"
    ENVIRONMENTAL_AUDIO_EXPOSURE_EVENT = "HKCategoryTypeIdentifierEnvironmentalAudioExposureEvent"
    HEADPHONE_AUDIO_EXPOSURE_EVENT = "HKCategoryTypeIdentifierHeadphoneAudioExposureEvent"

    """
    TEST RESULTS
    Values: 1 = negative, 2 = positive, 3 = indeterminate
    """
    PREGNANCY_TEST_RESULT = "HKCategoryTypeIdentifierPregnancyTestResult"
    PROGESTERONE_TEST_RESULT = "HKCategoryTypeIdentifierProgesteroneTestResult"

    """
    CONTRACEPTIVE METHODS
    Values: 1 = unspecified, 2 = implant, 3 = injection,
    4 = intrauterineDevice, 5 = intravaginalRing, 6 = oral, 7 = patch
    """
    CONTRACEPTIVE_METHODS = "HKCategoryTypeIdentifierContraceptive"

    """
    LAB RESULTS
    Values: 1 = unspecified, 2 = positive, 3 = negative
    """
    LAB_RESULTS = "HKCategoryTypeIdentifierLabResult"

    """
    LOSS OF SMELL OR TASTE   
    Values: 0 = present, 1 = notPresent
    """
    LOSS_OF_SMELL = "HKCategoryTypeIdentifierLossOfSmell"
    LOSS_OF_TASTE = "HKCategoryTypeIdentifierLossOfTaste"

    """
    APPETITE CHANGE   
    Values: 0 = unspecified, 1 = noChange, 2 = decreased, 3 = increased
    """
    APPETITE_CHANGE = "HKCategoryTypeIdentifierAppetiteChange"

    """
    WOMEN'S HEALTH
    Values: 0 = nonApplicable
    """
    INTERMENSTRUAL_BLEEDING = "HKCategoryTypeIdentifierIntermenstrualBleeding"
    INFREQUENT_MENSTRUAL_CYCLES = "HKCategoryTypeIdentifierInfrequentMenstrualCycles"
    IRREGULAR_MENSTRUAL_CYCLES = "HKCategoryTypeIdentifierIrregularMenstrualCycles"
    PERSISTENT_INTERMENSTRUAL_BLEEDING = "HKCategoryTypeIdentifierPersistentIntermenstrualBleeding"
    PROLONGED_MENSTRUAL_PERIODS = "HKCategoryTypeIdentifierProlongedMenstrualPeriods"
    LACTATION = "HKCategoryTypeIdentifierLactation"
    PREGNANCY = "HKCategoryTypeIdentifierPregnancy"

    """
    APPLE MOVE TIME AND STAND HOUR
    Values: 0 = nonApplicable (for move time), 0 = idle, 1 = stood (for stand hour)
    """
    APPLE_MOVE_TIME = "HKCategoryTypeIdentifierAppleMoveTime"
    APPLE_STAND_HOUR = "HKCategoryTypeIdentifierAppleStandHour"

    """
    PAIN
    Values: 0 = unspecified, 1 = notPresent, 2 = mild, 3 = moderate, 4 = severe
    """
    ABDOMINAL_CRAMPS = "HKCategoryTypeIdentifierAbdominalCramps"
    ACNE = "HKCategoryTypeIdentifierAcne"
    BLADDER_INCONTINENCE = "HKCategoryTypeIdentifierBladderIncontinence"
    BLOATING = "HKCategoryTypeIdentifierBloating"
    BREAST_PAIN = "HKCategoryTypeIdentifierBreastPain"
    CHEST_TIGHTNESS_OR_PAIN = "HKCategoryTypeIdentifierChestTightnessOrPain"
    CHILLS = "HKCategoryTypeIdentifierChills"
    CONSTIPATION = "HKCategoryTypeIdentifierConstipation"
    COUGHING = "HKCategoryTypeIdentifierCoughing"
    DIARRHEA = "HKCategoryTypeIdentifierDiarrhea"
    DIZZINESS = "HKCategoryTypeIdentifierDizziness"
    DRY_SKIN = "HKCategoryTypeIdentifierDrySkin"
    FAINTING = "HKCategoryTypeIdentifierFainting"
    FATIGUE = "HKCategoryTypeIdentifierFatigue"
    FEVER = "HKCategoryTypeIdentifierFever"
    GENERALIZED_BODY_ACHE = "HKCategoryTypeIdentifierGeneralizedBodyAche"
    HAIR_LOSS = "HKCategoryTypeIdentifierHairLoss"
    HEADACHE = "HKCategoryTypeIdentifierHeadache"
    HEARTBURN = "HKCategoryTypeIdentifierHeartburn"
    HOT_FLASHES = "HKCategoryTypeIdentifierHotFlashes"
    LOWER_BACK_PAIN = "HKCategoryTypeIdentifierLowerBackPain"
    MEMORY_LAPSE = "HKCategoryTypeIdentifierMemoryLapse"
    MOOD_CHANGES = "HKCategoryTypeIdentifierMoodChanges"
    NAUSEA = "HKCategoryTypeIdentifierNausea"
    NIGHT_SWEATS = "HKCategoryTypeIdentifierNightSweats"
    PELVIC_PAIN = "HKCategoryTypeIdentifierPelvicPain"
    RAPID_POUNDING_OR_FLUTTERING_HEARTBEAT = "HKCategoryTypeIdentifierRapidPoundingOrFlutteringHeartbeat"
    RUNNY_NOSE = "HKCategoryTypeIdentifierRunnyNose"
    SHORTNESS_OF_BREATH = "HKCategoryTypeIdentifierShortnessOfBreath"
    SINUS_CONGESTION = "HKCategoryTypeIdentifierSinusCongestion"
    SKIPPED_HEARTBEAT = "HKCategoryTypeIdentifierSkippedHeartbeat"
    SLEEP_CHANGES = "HKCategoryTypeIdentifierSleepChanges"
    SORE_THROAT = "HKCategoryTypeIdentifierSoreThroat"
    VAGINAL_DRYNESS = "HKCategoryTypeIdentifierVaginalDryness"
    VOMITING = "HKCategoryTypeIdentifierVomiting"
    WHEEZING = "HKCategoryTypeIdentifierWheezing"


# Category types set (for backwards compatibility and validation)
CATEGORY_TYPE_IDENTIFIERS: set[AppleCategoryType] = {
    AppleCategoryType.SLEEP_ANALYSIS,
}
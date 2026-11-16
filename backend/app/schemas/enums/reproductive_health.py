from enum import StrEnum


class ReproductiveHealthType(StrEnum):
    """What a reproductive health entry records, shared by HealthKit and Health Connect.

    Stored in ``event_record.type`` (at most 32 characters).
    """

    MENSTRUAL_FLOW = "menstrual_flow"
    # A period as one span (Health Connect). HealthKit marks the first flow entry instead.
    MENSTRUAL_PERIOD = "menstrual_period"
    INTERMENSTRUAL_BLEEDING = "intermenstrual_bleeding"
    CERVICAL_MUCUS = "cervical_mucus"
    OVULATION_TEST = "ovulation_test"
    PREGNANCY_TEST = "pregnancy_test"
    PROGESTERONE_TEST = "progesterone_test"
    SEXUAL_ACTIVITY = "sexual_activity"
    CONTRACEPTIVE = "contraceptive"
    PREGNANCY = "pregnancy"
    LACTATION = "lactation"
    # Cycle deviations HealthKit detects itself (iOS 16+), named as the Health app shows them.
    INFREQUENT_MENSTRUAL_CYCLES = "infrequent_menstrual_cycles"
    IRREGULAR_MENSTRUAL_CYCLES = "irregular_menstrual_cycles"
    PROLONGED_MENSTRUAL_PERIODS = "prolonged_menstrual_periods"
    PERSISTENT_SPOTTING = "persistent_spotting"


class MenstrualFlow(StrEnum):
    UNSPECIFIED = "unspecified"
    NONE = "none"
    LIGHT = "light"
    MEDIUM = "medium"
    HEAVY = "heavy"


class CervicalMucusAppearance(StrEnum):
    UNKNOWN = "unknown"
    DRY = "dry"
    STICKY = "sticky"
    CREAMY = "creamy"
    WATERY = "watery"
    EGG_WHITE = "egg_white"
    UNUSUAL = "unusual"


class CervicalMucusSensation(StrEnum):
    LIGHT = "light"
    MEDIUM = "medium"
    HEAVY = "heavy"


class OvulationTestResult(StrEnum):
    NEGATIVE = "negative"
    LH_SURGE = "lh_surge"
    ESTROGEN_SURGE = "estrogen_surge"
    INDETERMINATE = "indeterminate"


class HormoneTestResult(StrEnum):
    """Pregnancy (hCG) and progesterone test results."""

    NEGATIVE = "negative"
    POSITIVE = "positive"
    INDETERMINATE = "indeterminate"


class ContraceptiveMethod(StrEnum):
    UNSPECIFIED = "unspecified"
    IMPLANT = "implant"
    INJECTION = "injection"
    IUD = "iud"
    INTRAVAGINAL_RING = "intravaginal_ring"
    ORAL = "oral"
    PATCH = "patch"


# The values each type takes; a type not listed has none.
REPRODUCTIVE_HEALTH_VALUE_ENUMS: dict[ReproductiveHealthType, type[StrEnum]] = {
    ReproductiveHealthType.MENSTRUAL_FLOW: MenstrualFlow,
    ReproductiveHealthType.CERVICAL_MUCUS: CervicalMucusAppearance,
    ReproductiveHealthType.OVULATION_TEST: OvulationTestResult,
    ReproductiveHealthType.PREGNANCY_TEST: HormoneTestResult,
    ReproductiveHealthType.PROGESTERONE_TEST: HormoneTestResult,
    ReproductiveHealthType.CONTRACEPTIVE: ContraceptiveMethod,
}

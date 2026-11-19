"""HealthKit and Health Connect reproductive health types and values, mapped to one vocabulary.

The platforms number values differently (flow `2` is light on iOS, medium on Android), so each
value table is keyed by the SDK type it belongs to.
"""

from app.schemas.enums import (
    CervicalMucusAppearance,
    ContraceptiveMethod,
    HormoneTestResult,
    MenstrualFlow,
    OvulationTestResult,
    ReproductiveHealthType,
)

_HK = "HKCategoryTypeIdentifier"

# HealthKit names first, Health Connect after. Types missing from a platform have no entry.
SDK_TYPE_TO_REPRODUCTIVE_HEALTH_TYPE: dict[str, ReproductiveHealthType] = {
    f"{_HK}MenstrualFlow": ReproductiveHealthType.MENSTRUAL_FLOW,
    f"{_HK}IntermenstrualBleeding": ReproductiveHealthType.INTERMENSTRUAL_BLEEDING,
    f"{_HK}CervicalMucusQuality": ReproductiveHealthType.CERVICAL_MUCUS,
    f"{_HK}OvulationTestResult": ReproductiveHealthType.OVULATION_TEST,
    f"{_HK}PregnancyTestResult": ReproductiveHealthType.PREGNANCY_TEST,
    f"{_HK}ProgesteroneTestResult": ReproductiveHealthType.PROGESTERONE_TEST,
    f"{_HK}SexualActivity": ReproductiveHealthType.SEXUAL_ACTIVITY,
    f"{_HK}Contraceptive": ReproductiveHealthType.CONTRACEPTIVE,
    f"{_HK}Pregnancy": ReproductiveHealthType.PREGNANCY,
    f"{_HK}Lactation": ReproductiveHealthType.LACTATION,
    f"{_HK}InfrequentMenstrualCycles": ReproductiveHealthType.INFREQUENT_MENSTRUAL_CYCLES,
    f"{_HK}IrregularMenstrualCycles": ReproductiveHealthType.IRREGULAR_MENSTRUAL_CYCLES,
    f"{_HK}ProlongedMenstrualPeriods": ReproductiveHealthType.PROLONGED_MENSTRUAL_PERIODS,
    f"{_HK}PersistentIntermenstrualBleeding": ReproductiveHealthType.PERSISTENT_SPOTTING,
    "MENSTRUAL_FLOW": ReproductiveHealthType.MENSTRUAL_FLOW,
    "MENSTRUAL_PERIOD": ReproductiveHealthType.MENSTRUAL_PERIOD,
    "INTERMENSTRUAL_BLEEDING": ReproductiveHealthType.INTERMENSTRUAL_BLEEDING,
    "CERVICAL_MUCUS": ReproductiveHealthType.CERVICAL_MUCUS,
    "OVULATION_TEST": ReproductiveHealthType.OVULATION_TEST,
    "SEXUAL_ACTIVITY": ReproductiveHealthType.SEXUAL_ACTIVITY,
}

# What each platform can send, for the coverage matrix.
HEALTHKIT_REPRODUCTIVE_HEALTH_TYPES: frozenset[ReproductiveHealthType] = frozenset(
    t for sdk_type, t in SDK_TYPE_TO_REPRODUCTIVE_HEALTH_TYPE.items() if sdk_type.startswith(_HK)
)
HEALTH_CONNECT_REPRODUCTIVE_HEALTH_TYPES: frozenset[ReproductiveHealthType] = frozenset(
    t for sdk_type, t in SDK_TYPE_TO_REPRODUCTIVE_HEALTH_TYPE.items() if not sdk_type.startswith(_HK)
)

_HORMONE_TEST = {1: HormoneTestResult.NEGATIVE, 2: HormoneTestResult.POSITIVE, 3: HormoneTestResult.INDETERMINATE}

# An SDK type's `value` number -> normalized value. A type not listed carries no value: the entry
# itself is the signal (HealthKit sends 0, Health Connect 1).
SDK_REPRODUCTIVE_HEALTH_VALUES: dict[str, dict[int, str]] = {
    # HKCategoryValueMenstrualFlow
    f"{_HK}MenstrualFlow": {
        1: MenstrualFlow.UNSPECIFIED,
        2: MenstrualFlow.LIGHT,
        3: MenstrualFlow.MEDIUM,
        4: MenstrualFlow.HEAVY,
        5: MenstrualFlow.NONE,
    },
    # MenstruationFlowRecord.FLOW_*
    "MENSTRUAL_FLOW": {
        0: MenstrualFlow.UNSPECIFIED,
        1: MenstrualFlow.LIGHT,
        2: MenstrualFlow.MEDIUM,
        3: MenstrualFlow.HEAVY,
    },
    # HKCategoryValueCervicalMucusQuality
    f"{_HK}CervicalMucusQuality": {
        1: CervicalMucusAppearance.DRY,
        2: CervicalMucusAppearance.STICKY,
        3: CervicalMucusAppearance.CREAMY,
        4: CervicalMucusAppearance.WATERY,
        5: CervicalMucusAppearance.EGG_WHITE,
    },
    # CervicalMucusRecord.APPEARANCE_*
    "CERVICAL_MUCUS": {
        0: CervicalMucusAppearance.UNKNOWN,
        1: CervicalMucusAppearance.DRY,
        2: CervicalMucusAppearance.STICKY,
        3: CervicalMucusAppearance.CREAMY,
        4: CervicalMucusAppearance.WATERY,
        5: CervicalMucusAppearance.EGG_WHITE,
        6: CervicalMucusAppearance.UNUSUAL,
    },
    # HKCategoryValueOvulationTestResult
    f"{_HK}OvulationTestResult": {
        1: OvulationTestResult.NEGATIVE,
        2: OvulationTestResult.LH_SURGE,
        3: OvulationTestResult.INDETERMINATE,
        4: OvulationTestResult.ESTROGEN_SURGE,
    },
    # OvulationTestRecord.RESULT_*: "positive" is the LH surge, "high" the estrogen surge
    "OVULATION_TEST": {
        0: OvulationTestResult.INDETERMINATE,
        1: OvulationTestResult.LH_SURGE,
        2: OvulationTestResult.ESTROGEN_SURGE,
        3: OvulationTestResult.NEGATIVE,
    },
    # HKCategoryValuePregnancyTestResult, HKCategoryValueProgesteroneTestResult
    f"{_HK}PregnancyTestResult": _HORMONE_TEST,
    f"{_HK}ProgesteroneTestResult": _HORMONE_TEST,
    # HKCategoryValueContraceptive
    f"{_HK}Contraceptive": {
        1: ContraceptiveMethod.UNSPECIFIED,
        2: ContraceptiveMethod.IMPLANT,
        3: ContraceptiveMethod.INJECTION,
        4: ContraceptiveMethod.IUD,
        5: ContraceptiveMethod.INTRAVAGINAL_RING,
        6: ContraceptiveMethod.ORAL,
        7: ContraceptiveMethod.PATCH,
    },
}

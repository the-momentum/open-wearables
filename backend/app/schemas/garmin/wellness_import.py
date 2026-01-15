"""Garmin Health API wellness data schemas.

These schemas represent data from Garmin's Health API endpoints:
- /wellness-api/rest/sleeps
- /wellness-api/rest/dailies
- /wellness-api/rest/epochs
- /wellness-api/rest/bodyComps
- /wellness-api/rest/stressDetails
- /wellness-api/rest/pulseox
- /wellness-api/rest/respiration
"""

from pydantic import BaseModel, ConfigDict


class GarminSleepJSON(BaseModel):
    """Garmin sleep data from /wellness-api/rest/sleeps endpoint.

    Sleep summaries provide data about sleep duration and sleep level classification.
    """

    model_config = ConfigDict(populate_by_name=True)

    # Required fields
    summaryId: str
    startTimeInSeconds: int  # UTC Unix timestamp
    durationInSeconds: int

    # Optional identifiers
    userAccessToken: str | None = None
    calendarDate: str | None = None  # "2024-01-15"
    startTimeOffsetInSeconds: int | None = None  # Timezone offset

    # Sleep duration breakdown (in seconds)
    unmeasurableSleepDurationInSeconds: int | None = None
    deepSleepDurationInSeconds: int | None = None
    lightSleepDurationInSeconds: int | None = None
    remSleepDurationInSeconds: int | None = None
    awakeDurationInSeconds: int | None = None

    # Sleep levels map - detailed sleep stages with timestamps
    # Format: {"deep": [{"startTimeInSeconds": ..., "endTimeInSeconds": ...}], ...}
    sleepLevelsMap: dict | None = None

    # Validation type: "MANUAL", "AUTO_MANUAL", "DEVICE", "AUTO_TENTATIVE", etc.
    validation: str | None = None

    # Sleep scores
    overallSleepScore: dict | None = None
    sleepScoreQualifier: str | None = None
    sleepScoreFeedback: str | None = None
    sleepQualityType: str | None = None
    sleepRestlessnessQuality: str | None = None
    sleepScoreTimeInBedPenalty: int | None = None
    sleepScoreAwakePenalty: int | None = None

    # Heart rate during sleep
    averageHeartRate: int | None = None
    lowestHeartRate: int | None = None
    highestHeartRate: int | None = None

    # Respiration during sleep
    respirationAvg: float | None = None
    respirationLow: float | None = None
    respirationHigh: float | None = None
    avgWakingRespirationValue: float | None = None

    # SpO2 during sleep
    avgOxygenSaturation: float | None = None
    avgOxygenSaturationPercentage: float | None = None
    lowOxygenSaturationPercentage: float | None = None
    highOxygenSaturationPercentage: float | None = None

    # HRV during sleep
    sleepHRV: dict | None = None
    baselineSleepHRV: dict | None = None

    # Device info
    deviceRemCapable: bool | None = None


class GarminDailyJSON(BaseModel):
    """Garmin daily summary from /wellness-api/rest/dailies endpoint.

    Daily summaries contain wellness data on a daily basis such as steps,
    distance, heart rate, stress, and body battery.
    """

    model_config = ConfigDict(populate_by_name=True)

    # Required fields
    summaryId: str
    startTimeInSeconds: int  # UTC Unix timestamp
    durationInSeconds: int

    # Optional identifiers
    userAccessToken: str | None = None
    calendarDate: str | None = None  # "2024-01-15"
    startTimeOffsetInSeconds: int | None = None

    # Activity metrics
    steps: int | None = None
    distanceInMeters: float | None = None
    activeTimeInSeconds: int | None = None
    floorsClimbed: int | None = None
    floorsDescended: int | None = None

    # Calories
    activeKilocalories: int | None = None
    bmrKilocalories: int | None = None
    consumedCalories: int | None = None

    # Heart rate
    minHeartRateInBeatsPerMinute: int | None = None
    maxHeartRateInBeatsPerMinute: int | None = None
    averageHeartRateInBeatsPerMinute: int | None = None
    restingHeartRateInBeatsPerMinute: int | None = None
    # Heart rate samples: {"0": 65, "60": 68, ...} - offset in seconds -> bpm
    timeOffsetHeartRateSamples: dict[str, int] | None = None

    # Stress
    averageStressLevel: int | None = None
    maxStressLevel: int | None = None
    stressDurationInSeconds: int | None = None
    restStressDurationInSeconds: int | None = None
    activityStressDurationInSeconds: int | None = None
    lowStressDurationInSeconds: int | None = None
    mediumStressDurationInSeconds: int | None = None
    highStressDurationInSeconds: int | None = None
    stressQualifier: str | None = None

    # Body battery
    bodyBatteryChargedValue: int | None = None
    bodyBatteryDrainedValue: int | None = None
    bodyBatteryHighestValue: int | None = None
    bodyBatteryLowestValue: int | None = None
    bodyBatteryMostRecentValue: int | None = None
    bodyBatteryVersion: float | None = None

    # Intensity minutes
    moderateIntensityDurationInSeconds: int | None = None
    vigorousIntensityDurationInSeconds: int | None = None
    intensityDurationGoalInSeconds: int | None = None

    # Goals
    dailyStepGoal: int | None = None
    netCalorieGoal: int | None = None
    floorsClimbedGoal: int | None = None
    netKilocaloriesGoal: int | None = None

    # Hydration
    hydrationInMilliliters: int | None = None
    sweatLossInMilliliters: int | None = None

    # SpO2
    averageSpo2: float | None = None
    lowestSpo2: float | None = None

    # Respiration
    avgWakingRespirationValue: float | None = None
    highestRespirationValue: float | None = None
    lowestRespirationValue: float | None = None


class GarminEpochJSON(BaseModel):
    """Garmin epoch data from /wellness-api/rest/epochs endpoint.

    Epoch summaries contain information about wellness data broken down into
    15-minute intervals for a more granular representation.
    """

    model_config = ConfigDict(populate_by_name=True)

    # Required fields
    summaryId: str
    startTimeInSeconds: int  # UTC Unix timestamp
    durationInSeconds: int  # Typically 900 (15 minutes)

    # Optional identifiers
    userAccessToken: str | None = None
    startTimeOffsetInSeconds: int | None = None

    # Activity metrics
    activeTimeInSeconds: int | None = None
    steps: int | None = None
    distanceInMeters: float | None = None
    activeKilocalories: int | None = None
    met: float | None = None  # Metabolic equivalent of task

    # Intensity: "SEDENTARY", "ACTIVE", "HIGHLY_ACTIVE"
    intensity: str | None = None
    activityType: str | None = None

    # Heart rate
    meanHeartRateInBeatsPerMinute: int | None = None
    maxHeartRateInBeatsPerMinute: int | None = None


class GarminBodyCompJSON(BaseModel):
    """Garmin body composition from /wellness-api/rest/bodyComps endpoint.

    Body composition summaries provide metrics like weight, BMI, and body fat.
    """

    model_config = ConfigDict(populate_by_name=True)

    # Required fields
    summaryId: str
    measurementTimeInSeconds: int  # UTC Unix timestamp

    # Optional identifiers
    userAccessToken: str | None = None
    measurementTimeOffsetInSeconds: int | None = None

    # Body metrics
    weightInGrams: int | None = None
    bodyFatInPercent: float | None = None
    bodyMassIndex: float | None = None

    # Additional composition data
    muscleMassInGrams: int | None = None
    boneMassInGrams: int | None = None
    bodyWaterInPercent: float | None = None
    visceralFatMass: float | None = None
    basalMetabolicRateInKilocalories: int | None = None
    metabolicAge: int | None = None
    physiqueRating: int | None = None


class GarminStressJSON(BaseModel):
    """Garmin stress details from /wellness-api/rest/stressDetails endpoint.

    Stress details provide 3-minute granularity stress scores (1-100 range).
    """

    model_config = ConfigDict(populate_by_name=True)

    # Required fields
    summaryId: str
    startTimeInSeconds: int  # UTC Unix timestamp
    durationInSeconds: int

    # Optional identifiers
    userAccessToken: str | None = None
    startTimeOffsetInSeconds: int | None = None
    calendarDate: str | None = None

    # Stress data: {"0": 25, "180": 30, ...} - offset in seconds -> stress level (1-100)
    timeOffsetStressLevelValues: dict[str, int] | None = None

    # Body battery data: {"0": 75, "180": 74, ...} - offset in seconds -> body battery
    timeOffsetBodyBatteryValues: dict[str, int] | None = None


class GarminPulseOxJSON(BaseModel):
    """Garmin pulse oximetry from /wellness-api/rest/pulseox endpoint.

    SpO2 (blood oxygen saturation) measurements.
    """

    model_config = ConfigDict(populate_by_name=True)

    # Required fields
    summaryId: str
    startTimeInSeconds: int  # UTC Unix timestamp
    durationInSeconds: int

    # Optional identifiers
    userAccessToken: str | None = None
    startTimeOffsetInSeconds: int | None = None
    calendarDate: str | None = None

    # SpO2 data: {"0": 98, "300": 97, ...} - offset in seconds -> SpO2 percentage
    timeOffsetSpo2Values: dict[str, int] | None = None

    # On-demand readings
    onDemandReadings: list[dict] | None = None

    # Sleep SpO2
    sleepSpo2: dict | None = None


class GarminRespirationJSON(BaseModel):
    """Garmin respiration data from /wellness-api/rest/respiration endpoint.

    Breathing rate measurements.
    """

    model_config = ConfigDict(populate_by_name=True)

    # Required fields
    summaryId: str
    startTimeInSeconds: int  # UTC Unix timestamp
    durationInSeconds: int

    # Optional identifiers
    userAccessToken: str | None = None
    startTimeOffsetInSeconds: int | None = None
    calendarDate: str | None = None

    # Respiration data: {"0": 15.5, "300": 14.8, ...} - offset in seconds -> breaths/min
    timeOffsetRespirationValues: dict[str, float] | None = None

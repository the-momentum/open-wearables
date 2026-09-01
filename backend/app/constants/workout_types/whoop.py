import logging

from app.schemas.enums import WorkoutType
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)

# WHOOP sports. sport_name is a lowercase hyphenated slug ("hiking-rucking"), not the
# display name the docs table shows. sport_id is deprecated (nominally removed after
# 09/01/2025) but still sent, so it is kept as a fallback for unlisted slugs.
# Reference: https://developer.whoop.com/docs/developing/user-data/workout
# Format: (whoop_sport_name, whoop_sport_id, unified_type)
WHOOP_WORKOUT_TYPE_MAPPINGS: list[tuple[str, int, WorkoutType]] = [
    # Generic / catch-all
    ("activity", -1, WorkoutType.GENERIC),
    ("other", 71, WorkoutType.GENERIC),
    # Running & walking
    ("running", 0, WorkoutType.RUNNING),
    ("walking", 63, WorkoutType.WALKING),
    ("hiking-rucking", 52, WorkoutType.HIKING),
    ("track-field", 35, WorkoutType.RUNNING),
    ("stroller-walking", 252, WorkoutType.WALKING),
    ("stroller-jogging", 253, WorkoutType.RUNNING),
    ("dog-walking", 266, WorkoutType.WALKING),
    ("caddying", 93, WorkoutType.WALKING),
    ("toddlerwearing", 254, WorkoutType.WALKING),
    ("babywearing", 255, WorkoutType.WALKING),
    ("wheelchair-pushing", 105, WorkoutType.WHEELCHAIR),
    # Cycling
    ("cycling", 1, WorkoutType.CYCLING),
    ("mountain-biking", 57, WorkoutType.MOUNTAIN_BIKING),
    ("spin", 97, WorkoutType.INDOOR_CYCLING),
    ("assault-bike", 126, WorkoutType.INDOOR_CYCLING),
    # Swimming & water sports
    ("swimming", 33, WorkoutType.SWIMMING),
    ("water-polo", 37, WorkoutType.WATER_POLO),
    ("rowing", 18, WorkoutType.ROWING),
    ("kayaking", 55, WorkoutType.KAYAKING),
    ("paddleboarding", 61, WorkoutType.STAND_UP_PADDLEBOARDING),
    ("surfing", 64, WorkoutType.SURFING),
    ("sailing", 28, WorkoutType.SAILING),
    ("diving", 73, WorkoutType.DIVING),
    ("water-skiing", 267, WorkoutType.WATER_SKIING),
    ("wakeboarding", 268, WorkoutType.WAKEBOARDING),
    ("kite-boarding", 264, WorkoutType.KITESURFING),
    ("operations-water", 77, WorkoutType.OPERATIONS),
    # Strength & gym
    ("weightlifting", 45, WorkoutType.STRENGTH_TRAINING),
    ("powerlifting", 59, WorkoutType.STRENGTH_TRAINING),
    ("strength-trainer", 123, WorkoutType.STRENGTH_TRAINING),
    ("functional-fitness", 48, WorkoutType.CARDIO_TRAINING),
    ("elliptical", 65, WorkoutType.ELLIPTICAL),
    ("stairmaster", 66, WorkoutType.STAIR_CLIMBING),
    ("climber", 83, WorkoutType.STAIR_CLIMBING),
    ("stadium-steps", 261, WorkoutType.STAIR_CLIMBING),
    ("hiit", 96, WorkoutType.CARDIO_TRAINING),
    ("jumping-rope", 84, WorkoutType.CARDIO_TRAINING),
    ("obstacle-course-racing", 94, WorkoutType.CARDIO_TRAINING),
    ("parkour", 110, WorkoutType.PARKOUR),
    # Flexibility & mind-body
    ("yoga", 44, WorkoutType.YOGA),
    ("hot-yoga", 259, WorkoutType.YOGA),
    ("pilates", 43, WorkoutType.PILATES),
    ("stretching", 128, WorkoutType.STRETCHING),
    ("meditation", 70, WorkoutType.MEDITATION),
    ("barre", 107, WorkoutType.GROUP_EXERCISE),
    ("barre3", 258, WorkoutType.GROUP_EXERCISE),
    # Winter sports
    ("skiing", 29, WorkoutType.ALPINE_SKIING),
    ("cross-country-skiing", 47, WorkoutType.CROSS_COUNTRY_SKIING),
    ("snowboarding", 91, WorkoutType.SNOWBOARDING),
    ("ice-skating", 239, WorkoutType.ICE_SKATING),
    # Team sports - ball sports
    ("soccer", 30, WorkoutType.SOCCER),
    ("basketball", 17, WorkoutType.BASKETBALL),
    ("football", 21, WorkoutType.AMERICAN_FOOTBALL),
    ("australian-football", 85, WorkoutType.FOOTBALL),
    ("gaelic-football", 111, WorkoutType.FOOTBALL),
    ("baseball", 16, WorkoutType.BASEBALL),
    ("softball", 31, WorkoutType.BASEBALL),
    ("volleyball", 36, WorkoutType.VOLLEYBALL),
    ("rugby", 27, WorkoutType.RUGBY),
    ("lacrosse", 25, WorkoutType.LACROSSE),
    ("cricket", 100, WorkoutType.CRICKET),
    ("netball", 232, WorkoutType.SPORT),
    ("ultimate", 82, WorkoutType.SPORT),
    ("spikeball", 104, WorkoutType.SPORT),
    ("hurling-camogie", 112, WorkoutType.SPORT),
    ("paintball", 238, WorkoutType.SPORT),
    # Team sports - hockey
    ("ice-hockey", 24, WorkoutType.HOCKEY),
    ("field-hockey", 20, WorkoutType.HOCKEY),
    ("handball", 240, WorkoutType.HANDBALL),
    # Racket sports
    ("tennis", 34, WorkoutType.TENNIS),
    ("squash", 32, WorkoutType.SQUASH),
    ("badminton", 231, WorkoutType.BADMINTON),
    ("table-tennis", 230, WorkoutType.TABLE_TENNIS),
    ("padel", 249, WorkoutType.PADEL),
    ("paddle-tennis", 106, WorkoutType.PADEL),
    ("pickleball", 101, WorkoutType.PICKLEBALL),
    # Combat sports
    ("boxing", 39, WorkoutType.BOXING),
    ("kickboxing", 127, WorkoutType.BOXING),
    ("box-fitness", 103, WorkoutType.BOXING),
    ("martial-arts", 56, WorkoutType.MARTIAL_ARTS),
    ("jiu-jitsu", 98, WorkoutType.MARTIAL_ARTS),
    ("wrestling", 38, WorkoutType.WRESTLING),
    ("fencing", 19, WorkoutType.FENCING),
    # Climbing
    ("rock-climbing", 60, WorkoutType.ROCK_CLIMBING),
    # Golf
    ("golf", 22, WorkoutType.GOLF),
    ("disc-golf", 234, WorkoutType.DISC_SPORTS),
    # Skating
    ("inline-skating", 102, WorkoutType.INLINE_SKATING),
    ("skateboarding", 86, WorkoutType.SKATEBOARDING),
    # Equestrian
    ("horseback-riding", 53, WorkoutType.HORSEBACK_RIDING),
    ("polo", 262, WorkoutType.HORSEBACK_RIDING),
    # Multisport
    ("triathlon", 62, WorkoutType.TRIATHLON),
    ("duathlon", 49, WorkoutType.MULTISPORT),
    # Motor sports
    ("motocross", 92, WorkoutType.MOTORCYCLING),
    ("motor-racing", 95, WorkoutType.MOTOR_SPORTS),
    # Dance & group fitness
    ("dance", 42, WorkoutType.DANCE),
    ("circus-arts", 113, WorkoutType.DANCE),
    ("stage-performance", 108, WorkoutType.DANCE),
    ("f45-training", 248, WorkoutType.GROUP_EXERCISE),
    ("barrys", 250, WorkoutType.GROUP_EXERCISE),
    # Gymnastics
    ("gymnastics", 51, WorkoutType.GYMNASTICS),
    # Recovery & wellness
    ("ice-bath", 88, WorkoutType.RECOVERY),
    ("sauna", 233, WorkoutType.RECOVERY),
    ("massage-therapy", 121, WorkoutType.RECOVERY),
    ("air-compression", 236, WorkoutType.RECOVERY),
    ("percussive-massage", 237, WorkoutType.RECOVERY),
    # Military / operations
    ("operations-tactical", 74, WorkoutType.OPERATIONS),
    ("operations-medical", 75, WorkoutType.OPERATIONS),
    ("operations-flying", 76, WorkoutType.OPERATIONS),
    # Work & daily activities
    ("manual-labor", 99, WorkoutType.WORK),
    ("high-stress-work", 109, WorkoutType.WORK),
    ("coaching", 87, WorkoutType.WORK),
    ("watching-sports", 125, WorkoutType.LIFESTYLE),
    ("commuting", 89, WorkoutType.LIFESTYLE),
    ("gaming", 90, WorkoutType.GAMING),
    ("yard-work", 235, WorkoutType.CHORES),
    ("cooking", 269, WorkoutType.CHORES),
    ("cleaning", 270, WorkoutType.CHORES),
    ("public-speaking", 272, WorkoutType.LIFESTYLE),
    ("musical-performance", 263, WorkoutType.LIFESTYLE),
    ("dedicated-parenting", 251, WorkoutType.LIFESTYLE),
]

WHOOP_TO_UNIFIED: dict[str, WorkoutType] = {
    sport_name: unified_type for sport_name, _, unified_type in WHOOP_WORKOUT_TYPE_MAPPINGS
}

WHOOP_ID_TO_UNIFIED: dict[int, WorkoutType] = {
    sport_id: unified_type for _, sport_id, unified_type in WHOOP_WORKOUT_TYPE_MAPPINGS
}


def get_unified_workout_type(whoop_sport_name: str | None, whoop_sport_id: int | None = None) -> WorkoutType:
    """
    Convert Whoop sport to unified WorkoutType.

    Resolves by sport_name, then falls back to sport_id for sports whose slug is not
    listed. An unrecognised sport is logged rather than silently collapsing to OTHER,
    so a newly added Whoop sport is visible.

    Args:
        whoop_sport_name: Whoop sport_name slug (e.g. "running", "hiking-rucking")
        whoop_sport_id: Whoop numeric sport id (e.g. 0, 52), deprecated but still sent

    Returns:
        Unified WorkoutType enum value

    Examples:
        >>> get_unified_workout_type("running")
        WorkoutType.RUNNING
        >>> get_unified_workout_type("hiking-rucking")
        WorkoutType.HIKING
        >>> get_unified_workout_type(None, 52)
        WorkoutType.HIKING
        >>> get_unified_workout_type("unknown-sport")
        WorkoutType.OTHER

    Note:
        - Whoop sends lowercase hyphenated slugs, not the display names in its docs
        - If both fields are missing or unmapped, defaults to WorkoutType.OTHER
    """
    if whoop_sport_name:
        unified_type = WHOOP_TO_UNIFIED.get(whoop_sport_name.lower().strip())
        if unified_type is not None:
            return unified_type

    if whoop_sport_id is not None:
        unified_type = WHOOP_ID_TO_UNIFIED.get(whoop_sport_id)
        if unified_type is not None:
            return unified_type

    if whoop_sport_name or whoop_sport_id is not None:
        log_structured(
            logger,
            "warning",
            "Unmapped Whoop sport, falling back to OTHER",
            provider="whoop",
            sport_name=whoop_sport_name,
            sport_id=whoop_sport_id,
        )

    return WorkoutType.OTHER

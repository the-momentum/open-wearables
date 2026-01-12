from enum import StrEnum


class WorkoutType(StrEnum):
    """
    Unified workout/activity types for Polar, Suunto, and Garmin.

    Based on FIT SDK sport types and common activities across platforms.
    Excludes branded/niche activities (e.g., LES MILLS classes, specific dance types).
    """

    # Running & Walking
    RUNNING = "running"
    TRAIL_RUNNING = "trail_running"
    TREADMILL = "treadmill"
    WALKING = "walking"
    HIKING = "hiking"
    MOUNTAINEERING = "mountaineering"
    # Cycling
    CYCLING = "cycling"
    MOUNTAIN_BIKING = "mountain_biking"
    INDOOR_CYCLING = "indoor_cycling"
    CYCLOCROSS = "cyclocross"
    # Swimming
    SWIMMING = "swimming"
    POOL_SWIMMING = "pool_swimming"
    OPEN_WATER_SWIMMING = "open_water_swimming"
    # Strength & Gym
    STRENGTH_TRAINING = "strength_training"
    CARDIO_TRAINING = "cardio_training"
    FITNESS_EQUIPMENT = "fitness_equipment"
    ELLIPTICAL = "elliptical"
    ROWING_MACHINE = "rowing_machine"
    STAIR_CLIMBING = "stair_climbing"
    # Flexibility & Mind-Body
    YOGA = "yoga"
    PILATES = "pilates"
    STRETCHING = "stretching"
    # Winter Sports
    CROSS_COUNTRY_SKIING = "cross_country_skiing"
    ALPINE_SKIING = "alpine_skiing"
    BACKCOUNTRY_SKIING = "backcountry_skiing"
    DOWNHILL_SKIING = "downhill_skiing"
    SNOWBOARDING = "snowboarding"
    SNOWSHOEING = "snowshoeing"
    ICE_SKATING = "ice_skating"
    # Water Sports
    ROWING = "rowing"
    KAYAKING = "kayaking"
    CANOEING = "canoeing"
    PADDLING = "paddling"
    STAND_UP_PADDLEBOARDING = "stand_up_paddleboarding"
    SURFING = "surfing"
    KITESURFING = "kitesurfing"
    WINDSURFING = "windsurfing"
    SAILING = "sailing"
    # Team Sports
    SOCCER = "soccer"
    BASKETBALL = "basketball"
    FOOTBALL = "football"
    AMERICAN_FOOTBALL = "american_football"
    BASEBALL = "baseball"
    TENNIS = "tennis"
    BADMINTON = "badminton"
    VOLLEYBALL = "volleyball"
    HANDBALL = "handball"
    RUGBY = "rugby"
    HOCKEY = "hockey"
    FLOORBALL = "floorball"
    # Racket Sports
    SQUASH = "squash"
    TABLE_TENNIS = "table_tennis"
    PADEL = "padel"
    PICKLEBALL = "pickleball"

    # Combat Sports
    BOXING = "boxing"
    MARTIAL_ARTS = "martial_arts"

    # Outdoor Activities
    ROCK_CLIMBING = "rock_climbing"
    INDOOR_CLIMBING = "indoor_climbing"
    BOULDERING = "bouldering"
    TRAIL_HIKING = "trail_hiking"
    ORIENTEERING = "orienteering"
    # Other Sports
    GOLF = "golf"
    SKATING = "skating"
    INLINE_SKATING = "inline_skating"
    SKATEBOARDING = "skateboarding"
    HORSEBACK_RIDING = "horseback_riding"

    # Multisport
    TRIATHLON = "triathlon"
    MULTISPORT = "multisport"

    # Motor Sports
    MOTORCYCLING = "motorcycling"
    MOTOR_SPORTS = "motor_sports"

    # Dance & Group Fitness (non-branded)
    DANCE = "dance"
    AEROBICS = "aerobics"
    GROUP_EXERCISE = "group_exercise"

    # E-Sports & Alternative
    E_BIKING = "e_biking"
    VIRTUAL_ACTIVITY = "virtual_activity"

    # Diving
    DIVING = "diving"
    SNORKELING = "snorkeling"

    # Casual & General
    WALKING_FITNESS = "walking_fitness"
    CASUAL_WALKING = "casual_walking"

    # Transition (for multisport events)
    TRANSITION = "transition"

    # Generic/Other
    GENERIC = "generic"
    OTHER = "other"
    SPORT = "sport"

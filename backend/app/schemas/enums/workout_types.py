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
    MEDITATION = "meditation"
    # Winter Sports
    CROSS_COUNTRY_SKIING = "cross_country_skiing"
    ALPINE_SKIING = "alpine_skiing"
    BACKCOUNTRY_SKIING = "backcountry_skiing"
    DOWNHILL_SKIING = "downhill_skiing"
    SNOWBOARDING = "snowboarding"
    SNOWSHOEING = "snowshoeing"
    ICE_SKATING = "ice_skating"
    SNOWMOBILING = "snowmobiling"
    WINTER_SPORTS = "winter_sports"
    SNOW_SPORTS = "snow_sports"
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
    WATER_POLO = "water_polo"
    WAKEBOARDING = "wakeboarding"
    WATER_SKIING = "water_skiing"
    BOATING = "boating"
    WATER_SPORTS = "water_sports"
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
    LACROSSE = "lacrosse"
    CRICKET = "cricket"
    # Racket Sports
    SQUASH = "squash"
    TABLE_TENNIS = "table_tennis"
    PADEL = "padel"
    PICKLEBALL = "pickleball"
    RACQUETBALL = "racquetball"
    RACKET_SPORTS = "racket_sports"

    # Combat Sports
    BOXING = "boxing"
    MARTIAL_ARTS = "martial_arts"
    WRESTLING = "wrestling"
    FENCING = "fencing"

    # Outdoor Activities
    ROCK_CLIMBING = "rock_climbing"
    INDOOR_CLIMBING = "indoor_climbing"
    BOULDERING = "bouldering"
    TRAIL_HIKING = "trail_hiking"
    ORIENTEERING = "orienteering"
    ARCHERY = "archery"
    FISHING = "fishing"
    HUNTING = "hunting"
    PARAGLIDING = "paragliding"
    PARKOUR = "parkour"
    # Other Sports
    GOLF = "golf"
    SKATING = "skating"
    INLINE_SKATING = "inline_skating"
    SKATEBOARDING = "skateboarding"
    HORSEBACK_RIDING = "horseback_riding"
    GYMNASTICS = "gymnastics"
    BOWLING = "bowling"
    CURLING = "curling"
    DISC_SPORTS = "disc_sports"

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

    # Generic sport categories — broad groupings used when a more specific type is unavailable
    TEAM_SPORTS = "team_sports"
    PARA_SPORTS = "para_sports"
    PLAY = "play"
    WHEELCHAIR = "wheelchair"

    # Lifestyle & Wellness — non-sport activities tracked by some providers (e.g. WHOOP)
    RECOVERY = "recovery"
    GAMING = "gaming"
    CHORES = "chores"
    LIFESTYLE = "lifestyle"
    WORK = "work"
    OPERATIONS = "operations"

    # Generic/Other
    GENERIC = "generic"
    OTHER = "other"
    SPORT = "sport"


WORKOUTS_WITH_PACE = [
    # Running & Walking
    WorkoutType.RUNNING,
    WorkoutType.TRAIL_RUNNING,
    WorkoutType.TREADMILL,
    WorkoutType.WALKING,
    WorkoutType.HIKING,
    WorkoutType.MOUNTAINEERING,
    WorkoutType.TRAIL_HIKING,
    WorkoutType.WALKING_FITNESS,
    WorkoutType.CASUAL_WALKING,
    # Cycling
    WorkoutType.CYCLING,
    WorkoutType.MOUNTAIN_BIKING,
    WorkoutType.INDOOR_CYCLING,
    WorkoutType.CYCLOCROSS,
    WorkoutType.E_BIKING,
    # Swimming
    WorkoutType.SWIMMING,
    WorkoutType.POOL_SWIMMING,
    WorkoutType.OPEN_WATER_SWIMMING,
    # Water Sports
    WorkoutType.ROWING,
    WorkoutType.KAYAKING,
    WorkoutType.CANOEING,
    WorkoutType.PADDLING,
    WorkoutType.STAND_UP_PADDLEBOARDING,
    # Winter Sports
    WorkoutType.CROSS_COUNTRY_SKIING,
    WorkoutType.BACKCOUNTRY_SKIING,
    # Skating
    WorkoutType.SKATING,
    WorkoutType.INLINE_SKATING,
    WorkoutType.ICE_SKATING,
    # Multisport
    WorkoutType.TRIATHLON,
]

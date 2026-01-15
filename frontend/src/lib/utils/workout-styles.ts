export interface WorkoutStyle {
  emoji: string;
  label: string;
  bgColor: string; // Tailwind background color class
}

// Workout type to style configuration
// Keys are lowercase patterns to match against workout type
const WORKOUT_STYLE_CONFIG: Record<string, WorkoutStyle> = {
  // Running & Walking
  running: {
    emoji: '🏃',
    label: 'Running',
    bgColor: 'bg-indigo-500/10',
  },
  run: {
    emoji: '🏃',
    label: 'Running',
    bgColor: 'bg-indigo-500/10',
  },
  trail_running: {
    emoji: '🏃‍♂️',
    label: 'Trail Running',
    bgColor: 'bg-emerald-500/10',
  },
  treadmill: {
    emoji: '🏃',
    label: 'Treadmill',
    bgColor: 'bg-indigo-500/10',
  },
  walking: {
    emoji: '🚶',
    label: 'Walking',
    bgColor: 'bg-green-500/10',
  },
  walk: {
    emoji: '🚶',
    label: 'Walking',
    bgColor: 'bg-green-500/10',
  },
  hiking: {
    emoji: '🥾',
    label: 'Hiking',
    bgColor: 'bg-amber-500/10',
  },
  hike: {
    emoji: '🥾',
    label: 'Hiking',
    bgColor: 'bg-amber-500/10',
  },
  mountaineering: {
    emoji: '🧗',
    label: 'Mountaineering',
    bgColor: 'bg-stone-500/10',
  },
  climbing: {
    emoji: '🧗',
    label: 'Climbing',
    bgColor: 'bg-orange-500/10',
  },

  // Cycling
  cycling: {
    emoji: '🚴',
    label: 'Cycling',
    bgColor: 'bg-orange-500/10',
  },
  cycle: {
    emoji: '🚴',
    label: 'Cycling',
    bgColor: 'bg-orange-500/10',
  },
  bike: {
    emoji: '🚴',
    label: 'Cycling',
    bgColor: 'bg-orange-500/10',
  },
  biking: {
    emoji: '🚴',
    label: 'Cycling',
    bgColor: 'bg-orange-500/10',
  },
  mountain_biking: {
    emoji: '🚵',
    label: 'Mountain Biking',
    bgColor: 'bg-amber-500/10',
  },
  indoor_cycling: {
    emoji: '🚴',
    label: 'Indoor Cycling',
    bgColor: 'bg-orange-500/10',
  },

  // Swimming
  swimming: {
    emoji: '🏊',
    label: 'Swimming',
    bgColor: 'bg-blue-500/10',
  },
  swim: {
    emoji: '🏊',
    label: 'Swimming',
    bgColor: 'bg-blue-500/10',
  },
  pool_swimming: {
    emoji: '🏊',
    label: 'Pool Swimming',
    bgColor: 'bg-blue-500/10',
  },
  open_water_swimming: {
    emoji: '🏊‍♂️',
    label: 'Open Water',
    bgColor: 'bg-cyan-500/10',
  },

  // Strength & Gym
  strength_training: {
    emoji: '🏋️',
    label: 'Strength',
    bgColor: 'bg-amber-500/10',
  },
  strength: {
    emoji: '🏋️',
    label: 'Strength',
    bgColor: 'bg-amber-500/10',
  },
  weight: {
    emoji: '🏋️',
    label: 'Weights',
    bgColor: 'bg-amber-500/10',
  },
  gym: {
    emoji: '💪',
    label: 'Gym',
    bgColor: 'bg-amber-500/10',
  },
  fitness_equipment: {
    emoji: '🏋️',
    label: 'Fitness Equipment',
    bgColor: 'bg-zinc-500/10',
  },

  // Cardio
  cardio: {
    emoji: '❤️',
    label: 'Cardio',
    bgColor: 'bg-rose-500/10',
  },
  cardio_training: {
    emoji: '❤️',
    label: 'Cardio',
    bgColor: 'bg-rose-500/10',
  },
  hiit: {
    emoji: '🔥',
    label: 'HIIT',
    bgColor: 'bg-red-500/10',
  },
  aerobic: {
    emoji: '💨',
    label: 'Aerobic',
    bgColor: 'bg-sky-500/10',
  },
  elliptical: {
    emoji: '🦵',
    label: 'Elliptical',
    bgColor: 'bg-purple-500/10',
  },
  rowing: {
    emoji: '🚣',
    label: 'Rowing',
    bgColor: 'bg-teal-500/10',
  },
  rowing_machine: {
    emoji: '🚣',
    label: 'Rowing Machine',
    bgColor: 'bg-teal-500/10',
  },
  stair_climbing: {
    emoji: '🪜',
    label: 'Stair Climbing',
    bgColor: 'bg-violet-500/10',
  },

  // Mind & Body
  yoga: {
    emoji: '🧘',
    label: 'Yoga',
    bgColor: 'bg-pink-500/10',
  },
  pilates: {
    emoji: '🧘‍♀️',
    label: 'Pilates',
    bgColor: 'bg-fuchsia-500/10',
  },
  stretching: {
    emoji: '🤸',
    label: 'Stretching',
    bgColor: 'bg-lime-500/10',
  },
  meditation: {
    emoji: '🧘',
    label: 'Meditation',
    bgColor: 'bg-violet-500/10',
  },
  flexibility: {
    emoji: '🤸',
    label: 'Flexibility',
    bgColor: 'bg-pink-500/10',
  },

  // Winter Sports
  skiing: {
    emoji: '⛷️',
    label: 'Skiing',
    bgColor: 'bg-sky-500/10',
  },
  snowboarding: {
    emoji: '🏂',
    label: 'Snowboarding',
    bgColor: 'bg-cyan-500/10',
  },
  cross_country_skiing: {
    emoji: '🎿',
    label: 'Cross Country Skiing',
    bgColor: 'bg-blue-500/10',
  },
  ice_skating: {
    emoji: '⛸️',
    label: 'Ice Skating',
    bgColor: 'bg-sky-500/10',
  },

  // Ball Sports
  tennis: {
    emoji: '🎾',
    label: 'Tennis',
    bgColor: 'bg-lime-500/10',
  },
  badminton: {
    emoji: '🏸',
    label: 'Badminton',
    bgColor: 'bg-green-500/10',
  },
  table_tennis: {
    emoji: '🏓',
    label: 'Table Tennis',
    bgColor: 'bg-red-500/10',
  },
  golf: {
    emoji: '🏌️',
    label: 'Golf',
    bgColor: 'bg-green-500/10',
  },
  basketball: {
    emoji: '🏀',
    label: 'Basketball',
    bgColor: 'bg-orange-500/10',
  },
  soccer: {
    emoji: '⚽',
    label: 'Soccer',
    bgColor: 'bg-green-500/10',
  },
  football: {
    emoji: '🏈',
    label: 'Football',
    bgColor: 'bg-amber-500/10',
  },
  volleyball: {
    emoji: '🏐',
    label: 'Volleyball',
    bgColor: 'bg-yellow-500/10',
  },
  baseball: {
    emoji: '⚾',
    label: 'Baseball',
    bgColor: 'bg-red-500/10',
  },
  softball: {
    emoji: '🥎',
    label: 'Softball',
    bgColor: 'bg-yellow-500/10',
  },
  hockey: {
    emoji: '🏒',
    label: 'Hockey',
    bgColor: 'bg-blue-500/10',
  },
  rugby: {
    emoji: '🏉',
    label: 'Rugby',
    bgColor: 'bg-amber-500/10',
  },
  cricket: {
    emoji: '🏏',
    label: 'Cricket',
    bgColor: 'bg-green-500/10',
  },

  // Combat Sports
  boxing: {
    emoji: '🥊',
    label: 'Boxing',
    bgColor: 'bg-red-500/10',
  },
  martial_arts: {
    emoji: '🥋',
    label: 'Martial Arts',
    bgColor: 'bg-zinc-500/10',
  },
  kickboxing: {
    emoji: '🥊',
    label: 'Kickboxing',
    bgColor: 'bg-red-500/10',
  },
  wrestling: {
    emoji: '🤼',
    label: 'Wrestling',
    bgColor: 'bg-amber-500/10',
  },
  fencing: {
    emoji: '🤺',
    label: 'Fencing',
    bgColor: 'bg-zinc-500/10',
  },

  // Water Sports
  surfing: {
    emoji: '🏄',
    label: 'Surfing',
    bgColor: 'bg-cyan-500/10',
  },
  kayaking: {
    emoji: '🛶',
    label: 'Kayaking',
    bgColor: 'bg-teal-500/10',
  },
  canoeing: {
    emoji: '🛶',
    label: 'Canoeing',
    bgColor: 'bg-teal-500/10',
  },
  sailing: {
    emoji: '⛵',
    label: 'Sailing',
    bgColor: 'bg-blue-500/10',
  },
  water_polo: {
    emoji: '🤽',
    label: 'Water Polo',
    bgColor: 'bg-blue-500/10',
  },
  diving: {
    emoji: '🤿',
    label: 'Diving',
    bgColor: 'bg-cyan-500/10',
  },

  // Other
  dance: {
    emoji: '💃',
    label: 'Dance',
    bgColor: 'bg-pink-500/10',
  },
  dancing: {
    emoji: '💃',
    label: 'Dancing',
    bgColor: 'bg-pink-500/10',
  },
  gymnastics: {
    emoji: '🤸',
    label: 'Gymnastics',
    bgColor: 'bg-purple-500/10',
  },
  horse_riding: {
    emoji: '🏇',
    label: 'Horse Riding',
    bgColor: 'bg-amber-500/10',
  },
  archery: {
    emoji: '🏹',
    label: 'Archery',
    bgColor: 'bg-red-500/10',
  },
  skateboarding: {
    emoji: '🛹',
    label: 'Skateboarding',
    bgColor: 'bg-orange-500/10',
  },
  workout: {
    emoji: '⚡',
    label: 'Workout',
    bgColor: 'bg-yellow-500/10',
  },
  other: {
    emoji: '🏅',
    label: 'Activity',
    bgColor: 'bg-zinc-500/10',
  },
};

// Default fallback style
const DEFAULT_WORKOUT_STYLE: WorkoutStyle = {
  emoji: '🏅',
  label: 'Activity',
  bgColor: 'bg-zinc-500/10',
};

/**
 * Get workout style configuration based on workout type.
 * Matches exact type first, then searches for partial matches.
 */
export function getWorkoutStyle(type: string | null | undefined): WorkoutStyle {
  if (!type) return DEFAULT_WORKOUT_STYLE;

  const normalizedType = type.toLowerCase().trim();

  // Exact match first
  if (WORKOUT_STYLE_CONFIG[normalizedType]) {
    return WORKOUT_STYLE_CONFIG[normalizedType];
  }

  // Partial match - check if type contains any config key
  for (const [key, config] of Object.entries(WORKOUT_STYLE_CONFIG)) {
    if (normalizedType.includes(key) || key.includes(normalizedType)) {
      return config;
    }
  }

  // Return default with formatted label
  const formattedLabel = type
    .split(/[_\s]+/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');

  return {
    ...DEFAULT_WORKOUT_STYLE,
    label: formattedLabel,
  };
}

/**
 * Get just the emoji for a workout type.
 * Convenience function when you only need the emoji.
 */
export function getWorkoutEmoji(type: string | null | undefined): string {
  return getWorkoutStyle(type).emoji;
}

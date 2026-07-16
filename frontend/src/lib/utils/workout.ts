import { format } from 'date-fns';
import type { EventRecordResponse } from '@/lib/api/types';

/**
 * Workout category types for field configuration
 */
export type WorkoutCategory =
  | 'running'
  | 'cycling'
  | 'swimming'
  | 'strength'
  | 'cardio'
  | 'default';

/**
 * Field configuration for workout details
 */
export interface WorkoutFieldConfig {
  key: keyof EventRecordResponse;
  label: string;
  format: (value: unknown) => string;
}

/**
 * Field definitions with formatting functions
 */
export const WORKOUT_FIELD_DEFINITIONS: Record<string, WorkoutFieldConfig> = {
  start_time: {
    key: 'start_time',
    label: 'Start',
    format: (v) => (v ? format(new Date(v as string), 'h:mm a') : '-'),
  },
  end_time: {
    key: 'end_time',
    label: 'End',
    format: (v) => (v ? format(new Date(v as string), 'h:mm a') : '-'),
  },
  distance_meters: {
    key: 'distance_meters',
    label: 'Distance',
    format: (v) => {
      if (!v) return '-';
      const meters = Number(v);
      if (meters >= 1000) return `${(meters / 1000).toFixed(2)} km`;
      return `${Math.round(meters)} m`;
    },
  },
  steps_count: {
    key: 'steps_avg',
    label: 'Steps',
    format: (v) => (v ? Number(v).toLocaleString() : '-'),
  },
  avg_heart_rate_bpm: {
    key: 'avg_heart_rate_bpm',
    label: 'Avg HR',
    format: (v) => (v ? `${Math.round(Number(v))} bpm` : '-'),
  },
  max_heart_rate_bpm: {
    key: 'max_heart_rate_bpm',
    label: 'Max HR',
    format: (v) => (v ? `${Math.round(Number(v))} bpm` : '-'),
  },
  elevation_gain_meters: {
    key: 'elevation_gain_meters',
    label: 'Elevation',
    format: (v) => (v ? `${Math.round(Number(v))} m` : '-'),
  },
  average_speed: {
    key: 'average_speed',
    label: 'Avg Speed',
    format: (v) => (v ? `${Number(v).toFixed(1)} km/h` : '-'),
  },
  max_speed: {
    key: 'max_speed',
    label: 'Max Speed',
    format: (v) => (v ? `${Number(v).toFixed(1)} km/h` : '-'),
  },
  average_watts: {
    key: 'average_watts',
    label: 'Avg Power',
    format: (v) => (v ? `${Math.round(Number(v))} W` : '-'),
  },
  moving_time: {
    key: 'moving_time_seconds',
    label: 'Moving Time',
    format: (v) => {
      if (!v) return '-';
      const secs = Number(v);
      const mins = Math.floor(secs / 60);
      const hours = Math.floor(mins / 60);
      if (hours > 0) return `${hours}h ${mins % 60}m`;
      return `${mins}m`;
    },
  },
  source: {
    key: 'source',
    label: 'Source',
    format: (v) => {
      if (!v) return '-';
      const source = v as { provider?: string; device?: string };
      return source.provider || '-';
    },
  },
};

/**
 * Field keys to display for each workout category
 */
export const WORKOUT_CATEGORY_FIELDS: Record<WorkoutCategory, string[]> = {
  running: [
    'start_time',
    'end_time',
    'distance_meters',
    'steps_count',
    'avg_heart_rate_bpm',
    'max_heart_rate_bpm',
    'elevation_gain_meters',
    'average_speed',
    'source',
  ],
  cycling: [
    'start_time',
    'end_time',
    'distance_meters',
    'avg_heart_rate_bpm',
    'max_heart_rate_bpm',
    'elevation_gain_meters',
    'average_speed',
    'max_speed',
    'average_watts',
    'source',
  ],
  swimming: [
    'start_time',
    'end_time',
    'distance_meters',
    'avg_heart_rate_bpm',
    'max_heart_rate_bpm',
    'moving_time',
    'source',
  ],
  strength: [
    'start_time',
    'end_time',
    'avg_heart_rate_bpm',
    'max_heart_rate_bpm',
    'source',
  ],
  cardio: [
    'start_time',
    'end_time',
    'avg_heart_rate_bpm',
    'max_heart_rate_bpm',
    'steps_count',
    'source',
  ],
  default: [
    'start_time',
    'end_time',
    'distance_meters',
    'avg_heart_rate_bpm',
    'max_heart_rate_bpm',
    'source',
  ],
};

/**
 * Map workout type string to category
 */
export function getWorkoutCategory(type: string): WorkoutCategory {
  const lowerType = type.toLowerCase();

  if (
    lowerType.includes('run') ||
    lowerType.includes('walk') ||
    lowerType.includes('hik')
  ) {
    return 'running';
  }
  if (lowerType.includes('cycl') || lowerType.includes('bik')) {
    return 'cycling';
  }
  if (lowerType.includes('swim')) {
    return 'swimming';
  }
  if (
    lowerType.includes('strength') ||
    lowerType.includes('weight') ||
    lowerType.includes('gym')
  ) {
    return 'strength';
  }
  if (
    lowerType.includes('cardio') ||
    lowerType.includes('hiit') ||
    lowerType.includes('aerobic')
  ) {
    return 'cardio';
  }
  return 'default';
}

/**
 * Get workout detail fields with data for display
 */
export function getWorkoutDetailFields(
  workout: EventRecordResponse,
  category: WorkoutCategory
): { label: string; value: string }[] {
  const fieldKeys = WORKOUT_CATEGORY_FIELDS[category];

  return fieldKeys
    .map((key) => {
      const field = WORKOUT_FIELD_DEFINITIONS[key];
      if (!field) return null;

      const value = workout[field.key];
      if (value === null || value === undefined || value === '') return null;

      return {
        label: field.label,
        value: field.format(value),
      };
    })
    .filter(
      (field): field is { label: string; value: string } => field !== null
    );
}

/**
 * Aggregated workout statistics
 */
export interface WorkoutStats {
  count: number;
  totalDuration: number;
  totalCalories: number;
  totalDistance: number;
}

/**
 * Calculate aggregated statistics from workouts
 */
export function calculateWorkoutStats(
  workouts: EventRecordResponse[]
): WorkoutStats | null {
  if (workouts.length === 0) {
    return null;
  }

  const totalDuration = workouts.reduce(
    (sum, w) => sum + (Number(w.duration_seconds) || 0),
    0
  );
  const totalCalories = workouts.reduce(
    (sum, w) => sum + (Number(w.calories_kcal) || 0),
    0
  );
  const totalDistance = workouts.reduce(
    (sum, w) => sum + (Number(w.distance_meters) || 0),
    0
  );

  return {
    count: workouts.length,
    totalDuration,
    totalCalories,
    totalDistance,
  };
}

/**
 * Convert Date to unix timestamp string (seconds)
 */
export function dateToTimestamp(date: Date): string {
  return Math.floor(date.getTime() / 1000).toString();
}

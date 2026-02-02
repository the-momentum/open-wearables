import type { ActivitySummary } from '@/lib/api/types';
import { formatDistance, formatMinutes, formatNumber } from './format';

/**
 * Metric keys for activity summary cards
 */
export type ActivityMetricKey =
  | 'steps'
  | 'calories'
  | 'activeTime'
  | 'heartRate'
  | 'distance'
  | 'floors'
  | 'sedentary';

/**
 * Chart colors for each activity metric
 */
export const ACTIVITY_METRIC_CHART_COLORS: Record<ActivityMetricKey, string> = {
  steps: '#10b981',
  calories: '#f97316',
  activeTime: '#0ea5e9',
  heartRate: '#f43f5e',
  distance: '#a855f7',
  floors: '#f59e0b',
  sedentary: '#71717a',
};

/**
 * Aggregated activity statistics
 */
export interface ActivityStats {
  totalSteps: number;
  avgSteps: number;
  totalCalories: number;
  avgCalories: number;
  totalDistance: number;
  totalActiveMinutes: number;
  totalFloorsClimbed: number;
  totalSedentaryMinutes: number;
  avgHeartRate: number | null;
  daysTracked: number;
}

/**
 * Calculate aggregated statistics from activity summaries
 */
export function calculateActivityStats(
  summaries: ActivitySummary[]
): ActivityStats | null {
  if (summaries.length === 0) {
    return null;
  }

  // Sum totals
  const totalSteps = summaries.reduce((acc, s) => acc + (s.steps || 0), 0);
  const totalCalories = summaries.reduce(
    (acc, s) => acc + (s.active_calories_kcal || 0),
    0
  );
  const totalDistance = summaries.reduce(
    (acc, s) => acc + (s.distance_meters || 0),
    0
  );
  const totalActiveMinutes = summaries.reduce(
    (acc, s) => acc + (s.active_minutes || 0),
    0
  );
  const totalFloorsClimbed = summaries.reduce(
    (acc, s) => acc + (s.floors_climbed || 0),
    0
  );
  const totalSedentaryMinutes = summaries.reduce(
    (acc, s) => acc + (s.sedentary_minutes || 0),
    0
  );

  // Calculate averages
  const daysWithSteps = summaries.filter((s) => s.steps !== null).length;
  const daysWithCalories = summaries.filter(
    (s) => s.active_calories_kcal !== null
  ).length;

  // Heart rate stats (average of daily averages)
  const heartRates = summaries
    .map((s) => s.heart_rate?.avg_bpm)
    .filter((hr): hr is number => hr !== null);
  const avgHeartRate =
    heartRates.length > 0
      ? heartRates.reduce((a, b) => a + b, 0) / heartRates.length
      : null;

  return {
    totalSteps,
    avgSteps: daysWithSteps > 0 ? Math.round(totalSteps / daysWithSteps) : 0,
    totalCalories,
    avgCalories:
      daysWithCalories > 0 ? Math.round(totalCalories / daysWithCalories) : 0,
    totalDistance,
    totalActiveMinutes,
    totalFloorsClimbed,
    totalSedentaryMinutes,
    avgHeartRate,
    daysTracked: summaries.length,
  };
}

/**
 * Field definition for activity detail display
 */
interface ActivityFieldDefinition {
  key: string;
  label: string;
  getValue: (summary: ActivitySummary) => string | null;
}

/**
 * Configuration for activity detail fields
 */
const ACTIVITY_FIELD_DEFINITIONS: ActivityFieldDefinition[] = [
  {
    key: 'distance',
    label: 'Distance',
    getValue: (s) =>
      s.distance_meters !== null ? formatDistance(s.distance_meters) : null,
  },
  {
    key: 'floors',
    label: 'Floors Climbed',
    getValue: (s) =>
      s.floors_climbed !== null ? formatNumber(s.floors_climbed) : null,
  },
  {
    key: 'elevation',
    label: 'Elevation',
    getValue: (s) =>
      s.elevation_meters !== null
        ? `${Math.round(s.elevation_meters)} m`
        : null,
  },
  {
    key: 'totalCalories',
    label: 'Total Calories',
    getValue: (s) =>
      s.total_calories_kcal !== null
        ? formatNumber(s.total_calories_kcal)
        : null,
  },
  {
    key: 'sedentary',
    label: 'Sedentary Time',
    getValue: (s) =>
      s.sedentary_minutes !== null ? formatMinutes(s.sedentary_minutes) : null,
  },
  {
    key: 'maxHr',
    label: 'Max Heart Rate',
    getValue: (s) =>
      s.heart_rate?.max_bpm !== null ? `${s.heart_rate.max_bpm} bpm` : null,
  },
  {
    key: 'minHr',
    label: 'Min Heart Rate',
    getValue: (s) =>
      s.heart_rate?.min_bpm !== null ? `${s.heart_rate.min_bpm} bpm` : null,
  },
  {
    key: 'lightActivity',
    label: 'Light Activity',
    getValue: (s) =>
      s.intensity_minutes?.light !== null
        ? formatMinutes(s.intensity_minutes.light)
        : null,
  },
  {
    key: 'moderateActivity',
    label: 'Moderate Activity',
    getValue: (s) =>
      s.intensity_minutes?.moderate !== null
        ? formatMinutes(s.intensity_minutes.moderate)
        : null,
  },
  {
    key: 'vigorousActivity',
    label: 'Vigorous Activity',
    getValue: (s) =>
      s.intensity_minutes?.vigorous !== null
        ? formatMinutes(s.intensity_minutes.vigorous)
        : null,
  },
  {
    key: 'source',
    label: 'Source',
    getValue: (s) => s.source?.provider || null,
  },
];

/**
 * Get detail fields for an activity summary that have values
 */
export function getActivityDetailFields(
  summary: ActivitySummary
): { label: string; value: string }[] {
  return ACTIVITY_FIELD_DEFINITIONS.map((field) => ({
    label: field.label,
    value: field.getValue(summary),
  })).filter(
    (field): field is { label: string; value: string } => field.value !== null
  );
}

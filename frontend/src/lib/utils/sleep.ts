import type {
  SleepSession,
  SleepSummary,
  SleepStagesSummary,
} from '@/lib/api/types';
import { formatMinutes } from './format';

/**
 * Sleep stage type keys
 */
export type SleepStageKey = 'deep' | 'rem' | 'light' | 'awake';

/**
 * Color classes for sleep stages (Tailwind)
 */
export const SLEEP_STAGE_COLORS: Record<SleepStageKey, string> = {
  deep: 'bg-indigo-500',
  rem: 'bg-purple-500',
  light: 'bg-sky-400',
  awake: 'bg-zinc-500',
};

/**
 * Display labels for sleep stages
 */
export const SLEEP_STAGE_LABELS: Record<SleepStageKey, string> = {
  deep: 'Deep',
  rem: 'REM',
  light: 'Light',
  awake: 'Awake',
};

/**
 * Chart colors for sleep metrics (hex)
 */
export const SLEEP_METRIC_CHART_COLORS = {
  efficiency: '#10b981',
  duration: '#6366f1',
} as const;

/**
 * Sleep stage data for visualization
 */
export interface SleepStageData {
  key: SleepStageKey;
  minutes: number;
  pct: number;
  color: string;
  label: string;
}

/**
 * Transform sleep stages into display data
 */
export function getSleepStageData(
  stages: SleepStagesSummary | null | undefined
): SleepStageData[] {
  if (!stages) return [];

  const total =
    (stages.deep_minutes || 0) +
    (stages.rem_minutes || 0) +
    (stages.light_minutes || 0) +
    (stages.awake_minutes || 0);

  if (total === 0) return [];

  return [
    {
      key: 'deep',
      minutes: stages.deep_minutes || 0,
      pct: ((stages.deep_minutes || 0) / total) * 100,
      color: SLEEP_STAGE_COLORS.deep,
      label: SLEEP_STAGE_LABELS.deep,
    },
    {
      key: 'rem',
      minutes: stages.rem_minutes || 0,
      pct: ((stages.rem_minutes || 0) / total) * 100,
      color: SLEEP_STAGE_COLORS.rem,
      label: SLEEP_STAGE_LABELS.rem,
    },
    {
      key: 'light',
      minutes: stages.light_minutes || 0,
      pct: ((stages.light_minutes || 0) / total) * 100,
      color: SLEEP_STAGE_COLORS.light,
      label: SLEEP_STAGE_LABELS.light,
    },
    {
      key: 'awake',
      minutes: stages.awake_minutes || 0,
      pct: ((stages.awake_minutes || 0) / total) * 100,
      color: SLEEP_STAGE_COLORS.awake,
      label: SLEEP_STAGE_LABELS.awake,
    },
  ];
}

/**
 * Aggregated sleep statistics
 */
export interface SleepStats {
  avgDuration: number | null;
  avgEfficiency: number | null;
  nightsTracked: number;
  avgBedtime: number | null;
  stages: SleepStagesSummary | null;
  stagesTotal: number;
}

/**
 * Calculate aggregated statistics from sleep summaries
 */
export function calculateSleepStats(
  summaries: SleepSummary[]
): SleepStats | null {
  if (summaries.length === 0) {
    return null;
  }

  // Filter out null values for averaging
  const durations = summaries
    .map((s) => s.duration_minutes)
    .filter((d): d is number => d !== null);
  const efficiencies = summaries
    .map((s) => s.efficiency_percent)
    .filter((e): e is number => e !== null);

  // Aggregate sleep stages (calculate averages)
  const totalDeep = summaries.reduce(
    (acc, s) => acc + (s.stages?.deep_minutes || 0),
    0
  );
  const totalRem = summaries.reduce(
    (acc, s) => acc + (s.stages?.rem_minutes || 0),
    0
  );
  const totalLight = summaries.reduce(
    (acc, s) => acc + (s.stages?.light_minutes || 0),
    0
  );
  const totalAwake = summaries.reduce(
    (acc, s) => acc + (s.stages?.awake_minutes || 0),
    0
  );
  const nightCount = summaries.length;
  const avgDeep = nightCount > 0 ? totalDeep / nightCount : 0;
  const avgRem = nightCount > 0 ? totalRem / nightCount : 0;
  const avgLight = nightCount > 0 ? totalLight / nightCount : 0;
  const avgAwake = nightCount > 0 ? totalAwake / nightCount : 0;
  const avgStagesTotal = avgDeep + avgRem + avgLight + avgAwake;

  // Calculate average bedtime
  const bedtimes = summaries
    .map((s) => s.start_time)
    .filter((t): t is string => t !== null)
    .map((t) => {
      const date = new Date(t);
      // Convert to minutes from midnight, handling late night times
      let minutes = date.getHours() * 60 + date.getMinutes();
      // If before 6am, treat as previous day's evening
      if (minutes < 360) minutes += 1440;
      return minutes;
    });

  const avgBedtimeMinutes =
    bedtimes.length > 0
      ? bedtimes.reduce((a, b) => a + b, 0) / bedtimes.length
      : null;

  return {
    avgDuration:
      durations.length > 0
        ? durations.reduce((a, b) => a + b, 0) / durations.length
        : null,
    avgEfficiency:
      efficiencies.length > 0
        ? efficiencies.reduce((a, b) => a + b, 0) / efficiencies.length
        : null,
    nightsTracked: summaries.length,
    avgBedtime: avgBedtimeMinutes,
    // Use SleepStagesSummary format so we can reuse SleepStagesBar
    // Store averages (not totals) so tooltip shows avg per night
    stages:
      avgStagesTotal > 0
        ? {
            deep_minutes: avgDeep,
            rem_minutes: avgRem,
            light_minutes: avgLight,
            awake_minutes: avgAwake,
          }
        : null,
    stagesTotal: avgStagesTotal,
  };
}

/**
 * Field definition for sleep session detail display
 */
interface SleepFieldDefinition {
  key: string;
  label: string;
  getValue: (session: SleepSession) => string | null;
}

/**
 * Configuration for sleep session detail fields
 */
const SLEEP_FIELD_DEFINITIONS: SleepFieldDefinition[] = [
  {
    key: 'deepSleep',
    label: 'Deep Sleep',
    getValue: (s) =>
      s.stages?.deep_minutes != null
        ? formatMinutes(s.stages.deep_minutes)
        : null,
  },
  {
    key: 'remSleep',
    label: 'REM Sleep',
    getValue: (s) =>
      s.stages?.rem_minutes != null
        ? formatMinutes(s.stages.rem_minutes)
        : null,
  },
  {
    key: 'lightSleep',
    label: 'Light Sleep',
    getValue: (s) =>
      s.stages?.light_minutes != null
        ? formatMinutes(s.stages.light_minutes)
        : null,
  },
  {
    key: 'awake',
    label: 'Time Awake',
    getValue: (s) =>
      s.stages?.awake_minutes != null
        ? formatMinutes(s.stages.awake_minutes)
        : null,
  },
  {
    key: 'source',
    label: 'Source',
    getValue: (s) => s.source?.provider || null,
  },
];

/**
 * Get detail fields for a sleep session that have values
 */
export function getSleepSessionDetailFields(
  session: SleepSession
): { label: string; value: string }[] {
  return SLEEP_FIELD_DEFINITIONS.map((field) => ({
    label: field.label,
    value: field.getValue(session),
  })).filter(
    (field): field is { label: string; value: string } => field.value !== null
  );
}

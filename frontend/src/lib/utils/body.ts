import { formatDistanceToNow } from 'date-fns';
import {
  Activity,
  Calculator,
  Dumbbell,
  Heart,
  Percent,
  Ruler,
  Scale,
  Thermometer,
} from 'lucide-react';
import type {
  BloodPressure,
  BodyDailySummary,
  BodySummary,
} from '@/lib/api/types';
import {
  formatBmi,
  formatHeight,
  formatPercentDecimal,
  formatTemperature,
  formatWeight,
} from '@/lib/utils/format';

/**
 * BMI category with label and color class
 */
export interface BmiCategory {
  label: string;
  color: string;
}

/**
 * Get BMI category label and color based on BMI value
 */
export function getBmiCategory(bmi: number | null | undefined): BmiCategory {
  if (bmi === null || bmi === undefined) {
    return { label: '', color: 'text-zinc-500' };
  }
  if (bmi < 18.5) return { label: 'Underweight', color: 'text-sky-400' };
  if (bmi < 25) return { label: 'Normal', color: 'text-emerald-400' };
  if (bmi < 30) return { label: 'Overweight', color: 'text-amber-400' };
  return { label: 'Obese', color: 'text-rose-400' };
}

/**
 * Format the last updated timestamp for display
 */
export function formatLastUpdated(timestamp: string | null): string {
  if (!timestamp) return 'Unknown';
  try {
    return formatDistanceToNow(new Date(timestamp), { addSuffix: true });
  } catch {
    return 'Unknown';
  }
}

/**
 * Format period for display (e.g., "7-day average")
 */
export function formatAveragePeriod(days: number): string {
  return days === 1 ? 'Today' : `${days}-day average`;
}

/**
 * Format blood pressure reading for display
 */
export function formatBloodPressure(
  bp: BloodPressure | null | undefined
): string {
  if (!bp) return '-';
  const sys = bp.avg_systolic_mmhg;
  const dia = bp.avg_diastolic_mmhg;
  if (sys === null || dia === null) return '-';
  return `${sys}/${dia}`;
}

/**
 * Format heart rate value for display
 */
export function formatHeartRate(bpm: number | null | undefined): string {
  if (bpm === null || bpm === undefined) return '-';
  return String(bpm);
}

/**
 * Format HRV value for display
 */
export function formatHrv(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return '-';
  return String(Math.round(ms));
}

// ============================================================================
// Body metric definitions (mirrors the Activity tab's METRICS array)
// ============================================================================

export type BodyMetricKey =
  | 'weight'
  | 'height'
  | 'bodyFat'
  | 'muscleMass'
  | 'bmi'
  | 'restingHeartRate'
  | 'hrv'
  | 'bodyTemp'
  | 'bloodPressure';

export interface BodyMetricDefinition {
  key: BodyMetricKey;
  label: string;
  shortLabel: string;
  icon: React.ElementType;
  color: string;
  bgColor: string;
  glowColor: string;
  chartColor: string;
  /** Format the headline card value from a BodySummary snapshot */
  getCardValue: (summary: BodySummary | null | undefined) => string;
  /** Card sublabel (e.g. timestamp). Returns undefined to omit. */
  getCardSublabel?: (
    summary: BodySummary | null | undefined
  ) => string | undefined;
  /**
   * Get the chart Y value(s) from a daily-summary row.
   *
   * Returns a single number for most metrics, or an object for compound metrics
   * (Blood Pressure: { systolic, diastolic }).
   */
  getChartValue: (
    row: BodyDailySummary
  ) => number | null | { systolic: number | null; diastolic: number | null };
  /** Y-axis tick formatter */
  formatChartTick: (value: number) => string;
  unit: string;
}

export const BODY_METRICS: BodyMetricDefinition[] = [
  {
    key: 'weight',
    label: 'Weight',
    shortLabel: 'Weight',
    icon: Scale,
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/10',
    glowColor: 'shadow-[0_0_15px_rgba(96,165,250,0.5)]',
    chartColor: 'hsl(217 91% 60%)',
    getCardValue: (s) => formatWeight(s?.slow_changing?.weight_kg ?? null),
    getChartValue: (row) => row.weight_kg,
    formatChartTick: (v) => `${v.toFixed(0)}`,
    unit: 'kg',
  },
  {
    key: 'height',
    label: 'Height',
    shortLabel: 'Height',
    icon: Ruler,
    color: 'text-cyan-400',
    bgColor: 'bg-cyan-500/10',
    glowColor: 'shadow-[0_0_15px_rgba(34,211,238,0.5)]',
    chartColor: 'hsl(189 94% 56%)',
    getCardValue: (s) => formatHeight(s?.slow_changing?.height_cm ?? null),
    getChartValue: (row) => row.height_cm,
    formatChartTick: (v) => `${v.toFixed(0)}`,
    unit: 'cm',
  },
  {
    key: 'bodyFat',
    label: 'Body Fat',
    shortLabel: 'Body Fat',
    icon: Percent,
    color: 'text-orange-400',
    bgColor: 'bg-orange-500/10',
    glowColor: 'shadow-[0_0_15px_rgba(251,146,60,0.5)]',
    chartColor: 'hsl(27 96% 61%)',
    getCardValue: (s) =>
      formatPercentDecimal(s?.slow_changing?.body_fat_percent ?? null),
    getChartValue: (row) => row.body_fat_percent,
    formatChartTick: (v) => `${v.toFixed(0)}%`,
    unit: '%',
  },
  {
    key: 'muscleMass',
    label: 'Muscle Mass',
    shortLabel: 'Muscle Mass',
    icon: Dumbbell,
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/10',
    glowColor: 'shadow-[0_0_15px_rgba(52,211,153,0.5)]',
    chartColor: 'hsl(160 84% 45%)',
    getCardValue: (s) => formatWeight(s?.slow_changing?.muscle_mass_kg ?? null),
    getChartValue: (row) => row.muscle_mass_kg,
    formatChartTick: (v) => `${v.toFixed(0)}`,
    unit: 'kg',
  },
  {
    key: 'bmi',
    label: 'BMI',
    shortLabel: 'BMI',
    icon: Calculator,
    color: 'text-purple-400',
    bgColor: 'bg-purple-500/10',
    glowColor: 'shadow-[0_0_15px_rgba(168,85,247,0.5)]',
    chartColor: 'hsl(271 91% 65%)',
    getCardValue: (s) => formatBmi(s?.slow_changing?.bmi ?? null),
    getChartValue: (row) => row.bmi,
    formatChartTick: (v) => v.toFixed(1),
    unit: '',
  },
  {
    key: 'restingHeartRate',
    label: 'Resting HR',
    shortLabel: 'Resting HR',
    icon: Heart,
    color: 'text-rose-400',
    bgColor: 'bg-rose-500/10',
    glowColor: 'shadow-[0_0_15px_rgba(244,63,94,0.5)]',
    chartColor: 'hsl(346 87% 60%)',
    getCardValue: (s) => formatHeartRate(s?.averaged?.resting_heart_rate_bpm),
    getChartValue: (row) => row.resting_heart_rate_bpm,
    formatChartTick: (v) => `${v.toFixed(0)}`,
    unit: 'bpm',
  },
  {
    key: 'hrv',
    label: 'HRV',
    shortLabel: 'HRV',
    icon: Activity,
    color: 'text-indigo-400',
    bgColor: 'bg-indigo-500/10',
    glowColor: 'shadow-[0_0_15px_rgba(129,140,248,0.5)]',
    chartColor: 'hsl(239 84% 67%)',
    getCardValue: (s) => formatHrv(s?.averaged?.avg_hrv_sdnn_ms),
    getChartValue: (row) => row.avg_hrv_sdnn_ms,
    formatChartTick: (v) => `${v.toFixed(0)}`,
    unit: 'ms',
  },
  {
    key: 'bodyTemp',
    label: 'Body Temp',
    shortLabel: 'Body Temp',
    icon: Thermometer,
    color: 'text-amber-400',
    bgColor: 'bg-amber-500/10',
    glowColor: 'shadow-[0_0_15px_rgba(245,158,11,0.5)]',
    chartColor: 'hsl(43 96% 56%)',
    getCardValue: (s) =>
      formatTemperature(s?.latest?.body_temperature_celsius ?? null),
    getCardSublabel: (s) =>
      s?.latest?.body_temperature_measured_at
        ? formatLastUpdated(s.latest.body_temperature_measured_at)
        : undefined,
    getChartValue: (row) => row.body_temperature_celsius,
    formatChartTick: (v) => v.toFixed(1),
    unit: '°C',
  },
  {
    key: 'bloodPressure',
    label: 'Blood Pressure',
    shortLabel: 'Blood Pressure',
    icon: Activity,
    color: 'text-red-400',
    bgColor: 'bg-red-500/10',
    glowColor: 'shadow-[0_0_15px_rgba(248,113,113,0.5)]',
    chartColor: 'hsl(0 84% 60%)',
    getCardValue: (s) => formatBloodPressure(s?.latest?.blood_pressure),
    getCardSublabel: (s) =>
      s?.latest?.blood_pressure_measured_at
        ? formatLastUpdated(s.latest.blood_pressure_measured_at)
        : undefined,
    getChartValue: (row) => ({
      systolic: row.blood_pressure?.avg_systolic_mmhg ?? null,
      diastolic: row.blood_pressure?.avg_diastolic_mmhg ?? null,
    }),
    formatChartTick: (v) => `${v.toFixed(0)}`,
    unit: 'mmHg',
  },
];

export const BODY_COMPOSITION_KEYS: BodyMetricKey[] = [
  'weight',
  'height',
  'bodyFat',
  'muscleMass',
  'bmi',
];
export const BODY_VITALS_KEYS: BodyMetricKey[] = ['restingHeartRate', 'hrv'];
export const BODY_RECENT_READING_KEYS: BodyMetricKey[] = [
  'bodyTemp',
  'bloodPressure',
];

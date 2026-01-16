import { format } from 'date-fns';
import type { BodySummary } from '@/lib/api/types';

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
 * Body composition data extracted from summaries
 */
export interface BodyComposition {
  weight: number | null;
  height: number | null;
  bodyFat: number | null;
  muscleMass: number | null;
  bmi: number | null;
}

/**
 * Get the latest body summary that has meaningful data
 */
export function getLatestBodySummary(
  summaries: BodySummary[]
): BodySummary | null {
  if (summaries.length === 0) return null;

  // Sort by date descending
  const sorted = [...summaries].sort(
    (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()
  );

  // Find the most recent summary that has at least some data
  for (const s of sorted) {
    if (
      s.weight_kg !== null ||
      s.resting_heart_rate_bpm !== null ||
      s.avg_hrv_sdnn_ms !== null
    ) {
      return s;
    }
  }
  return sorted[0] || null;
}

/**
 * Extract body composition from summaries, finding the latest non-null value for each metric
 */
export function getBodyComposition(
  summaries: BodySummary[]
): BodyComposition | null {
  if (summaries.length === 0) return null;

  const sorted = [...summaries].sort(
    (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()
  );

  const findLatest = <T>(getter: (s: BodySummary) => T | null): T | null => {
    for (const s of sorted) {
      const val = getter(s);
      if (val !== null) return val;
    }
    return null;
  };

  return {
    weight: findLatest((s) => s.weight_kg),
    height: findLatest((s) => s.height_cm),
    bodyFat: findLatest((s) => s.body_fat_percent),
    muscleMass: findLatest((s) => s.muscle_mass_kg),
    bmi: findLatest((s) => s.bmi),
  };
}

/**
 * Weight chart data point
 */
export interface WeightChartDataPoint {
  date: string;
  weight: number | null;
}

/**
 * Prepare weight data for chart display
 */
export function prepareWeightChartData(
  summaries: BodySummary[]
): WeightChartDataPoint[] {
  const withWeight = summaries.filter((s) => s.weight_kg != null);
  if (withWeight.length === 0) return [];

  return [...withWeight]
    .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
    .map((s) => ({
      date: format(new Date(s.date), 'MMM d'),
      weight: s.weight_kg,
    }));
}

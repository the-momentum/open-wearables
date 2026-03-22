import { describe, expect, it } from 'vitest';
import { calculateActivityStats } from './activity';
import type { ActivitySummary } from '@/lib/api/types';

/** Create an ActivitySummary with all fields defaulting to null, overridable for specific test scenarios. */
function makeSummary(
  overrides: Partial<ActivitySummary> = {}
): ActivitySummary {
  return {
    date: '2026-01-01',
    source: { provider: 'apple_health', device: null },
    steps: null,
    distance_meters: null,
    floors_climbed: null,
    elevation_meters: null,
    active_calories_kcal: null,
    total_calories_kcal: null,
    active_minutes: null,
    sedentary_minutes: null,
    intensity_minutes: null,
    heart_rate: null,
    ...overrides,
  };
}

describe('calculateActivityStats', () => {
  it('returns null for empty summaries', () => {
    expect(calculateActivityStats([])).toBeNull();
  });

  it('calculates average heart rate from daily averages', () => {
    const summaries = [
      makeSummary({
        heart_rate: { avg_bpm: 70, max_bpm: 120, min_bpm: 55 },
      }),
      makeSummary({
        heart_rate: { avg_bpm: 80, max_bpm: 130, min_bpm: 60 },
      }),
    ];

    const stats = calculateActivityStats(summaries);
    expect(stats?.avgHeartRate).toBe(75);
  });

  it('returns null avgHeartRate when all days have null heart_rate', () => {
    const summaries = [
      makeSummary({ heart_rate: null }),
      makeSummary({ heart_rate: null }),
    ];

    const stats = calculateActivityStats(summaries);
    expect(stats?.avgHeartRate).toBeNull();
  });

  it('does not produce NaN when heart_rate is null for some days', () => {
    const summaries = [
      makeSummary({
        heart_rate: { avg_bpm: 72, max_bpm: 110, min_bpm: 58 },
      }),
      makeSummary({ heart_rate: null }),
      makeSummary({ heart_rate: null }),
    ];

    const stats = calculateActivityStats(summaries);
    expect(stats?.avgHeartRate).toBe(72);
    expect(Number.isNaN(stats?.avgHeartRate)).toBe(false);
  });

  it('does not produce NaN when avg_bpm is null inside heart_rate', () => {
    const summaries = [
      makeSummary({
        heart_rate: { avg_bpm: null, max_bpm: 120, min_bpm: 55 },
      }),
      makeSummary({
        heart_rate: { avg_bpm: 80, max_bpm: 130, min_bpm: 60 },
      }),
    ];

    const stats = calculateActivityStats(summaries);
    expect(stats?.avgHeartRate).toBe(80);
    expect(Number.isNaN(stats?.avgHeartRate)).toBe(false);
  });

  it('returns null avgHeartRate when every summary has avg_bpm null', () => {
    const summaries = [
      makeSummary({
        heart_rate: { avg_bpm: null, max_bpm: 120, min_bpm: 55 },
      }),
      makeSummary({
        heart_rate: { avg_bpm: null, max_bpm: 130, min_bpm: 60 },
      }),
    ];

    const stats = calculateActivityStats(summaries);
    expect(stats?.avgHeartRate).toBeNull();
    expect(Number.isNaN(stats?.avgHeartRate)).toBe(false);
  });

  it('sums steps and calculates average correctly', () => {
    const summaries = [
      makeSummary({ steps: 5000 }),
      makeSummary({ steps: 10000 }),
      makeSummary({ steps: null }),
    ];

    const stats = calculateActivityStats(summaries);
    expect(stats?.totalSteps).toBe(15000);
    expect(stats?.avgSteps).toBe(7500);
  });
});

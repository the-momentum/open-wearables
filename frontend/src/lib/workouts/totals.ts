import type { WorkoutTotalsResponse } from './types';

export type WorkoutTotals = {
	count: number;
	seconds: number;
	calories: number;
	meters: number;
	/** Always false: the database adds up every matching workout, not a page of them. */
	partial: boolean;
};

export const toWorkoutTotals = (totals: WorkoutTotalsResponse): WorkoutTotals => ({
	count: totals.count,
	seconds: totals.duration_seconds,
	calories: totals.calories_kcal ?? 0,
	meters: totals.distance_meters ?? 0,
	partial: false
});

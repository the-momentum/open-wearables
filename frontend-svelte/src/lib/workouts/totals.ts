import { isPartial, sumOf } from '$lib/events/totals';
import type { Workout } from './types';

export type WorkoutTotals = {
	count: number;
	seconds: number;
	calories: number;
	meters: number;
	/** The period holds more workouts than could be added up. */
	partial: boolean;
};

export function sumWorkouts(workouts: Workout[], total: number | null): WorkoutTotals {
	return {
		count: total ?? workouts.length,
		seconds: sumOf(workouts, (workout) => workout.duration_seconds),
		calories: sumOf(workouts, (workout) => workout.calories_kcal),
		meters: sumOf(workouts, (workout) => workout.distance_meters),
		partial: isPartial(workouts.length, total)
	};
}

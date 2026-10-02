import { isPartial, meanOf, sumOf } from '$lib/events/totals';
import type { ActivityDay } from './types';

export type ActivityTotals = {
	/** Days the provider had something for, which is the question behind the rest. */
	count: number;
	steps: number;
	meters: number;
	activeCalories: number;
	averageSteps: number | null;
	partial: boolean;
};

export function sumActivity(
	days: ActivityDay[],
	total: number | null,
	hasMore: boolean
): ActivityTotals {
	return {
		count: total ?? days.length,
		steps: sumOf(days, (day) => day.steps),
		meters: sumOf(days, (day) => day.distance_meters),
		activeCalories: sumOf(days, (day) => day.active_calories_kcal),
		// Mean over the days that reported steps: a day with none is a gap in the
		// data, not a day someone spent still.
		averageSteps: meanOf(days, (day) => day.steps),
		partial: isPartial(hasMore)
	};
}

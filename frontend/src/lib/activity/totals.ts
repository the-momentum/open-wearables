import type { ActivityTotalsResponse } from './types';

export type ActivityTotals = {
	/** Days the provider had something for, which is the question behind the rest. */
	count: number;
	steps: number;
	meters: number;
	activeCalories: number;
	/** Over the days that reported steps: a day with none is a gap, not a day spent still. */
	averageSteps: number | null;
	/** Always false: the API adds up every day in the period, not a page of them. */
	partial: boolean;
};

export const toActivityTotals = (totals: ActivityTotalsResponse): ActivityTotals => ({
	count: totals.days,
	steps: totals.steps,
	meters: totals.distance_meters,
	activeCalories: totals.active_calories_kcal,
	averageSteps: totals.avg_steps,
	partial: false
});

import { isPartial, meanOf } from '$lib/events/totals';
import { cycleDays } from './phases';
import type { Cycle } from './types';

export type CycleTotals = {
	count: number;
	/** Mean over the cycles that were measured, never over the predicted ones. */
	averageLength: number | null;
	averagePeriod: number | null;
	partial: boolean;
};

export function sumCycles(cycles: Cycle[], total: number | null, hasMore: boolean): CycleTotals {
	// A predicted cycle's length is a forecast, and averaging it in would make
	// the figure describe the provider's model rather than the person.
	const lived = cycles.filter((cycle) => !cycle.is_predicted_cycle);

	return {
		count: total ?? cycles.length,
		averageLength: meanOf(lived, cycleDays),
		averagePeriod: meanOf(lived, (cycle) => cycle.period_length),
		partial: isPartial(hasMore)
	};
}

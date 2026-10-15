import type { SleepTotalsResponse } from './types';

export type SleepTotals = {
	count: number;
	/** Nights and naps are both sessions, but only nights answer "how much sleep". */
	naps: number;
	asleepSeconds: number;
	inBedSeconds: number;
	efficiency: number | null;
	/** Always false: the database adds up every matching session, not a page of them. */
	partial: boolean;
};

export const toSleepTotals = (totals: SleepTotalsResponse): SleepTotals => ({
	count: totals.count,
	naps: totals.naps,
	asleepSeconds: totals.sleep_duration_seconds,
	inBedSeconds: totals.time_in_bed_seconds,
	efficiency: totals.avg_efficiency_percent,
	partial: false
});

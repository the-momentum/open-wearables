import { isPartial, meanOf, sumOf } from '$lib/events/totals';
import type { SleepSession } from './types';

export type SleepTotals = {
	count: number;
	/** Nights and naps are both sessions, but only nights answer "how much sleep". */
	naps: number;
	asleepSeconds: number;
	inBedSeconds: number;
	efficiency: number | null;
	partial: boolean;
};

export function sumSleep(sessions: SleepSession[], total: number | null): SleepTotals {
	return {
		count: total ?? sessions.length,
		naps: sessions.filter((session) => session.is_nap).length,
		asleepSeconds: sumOf(sessions, (session) => session.sleep_duration_seconds),
		// A provider that sends no time in bed still recorded a span.
		inBedSeconds: sumOf(
			sessions,
			(session) => session.time_in_bed_seconds ?? session.duration_seconds
		),
		efficiency: meanOf(sessions, (session) => session.efficiency_percent),
		partial: isPartial(sessions.length, total)
	};
}

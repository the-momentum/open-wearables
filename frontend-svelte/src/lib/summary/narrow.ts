import type { DataSummary } from './types';

/**
 * The summary as one provider sees it. Absent from `by_provider` means it
 * delivered nothing in the period, so zeroes — not everyone's totals.
 */
export function narrowToProvider(summary: DataSummary, provider: string): DataSummary {
	const only = summary.by_provider.find((entry) => entry.provider === provider);

	return {
		...summary,
		total_data_points: only?.data_points ?? 0,
		total_workouts: only?.workout_count ?? 0,
		total_sleep_events: only?.sleep_count ?? 0,
		series_type_counts: only?.series_counts ?? {}
	};
}

import type { DataSummary, ProviderDataCount } from './types';

/** The figures above the fold; per-type counts come from the timelines. */
export type Totals = Pick<
	DataSummary,
	'total_data_points' | 'total_workouts' | 'total_sleep_events'
>;

/**
 * Totals as one provider sees them. Absent from `by_provider` means it
 * delivered nothing in the period, so zeroes — not everyone's totals.
 */
export function narrowToProvider(summary: DataSummary, provider: string): Totals {
	const only = summary.by_provider.find((entry) => entry.provider === provider);

	return {
		total_data_points: only?.data_points ?? 0,
		total_workouts: only?.workout_count ?? 0,
		total_sleep_events: only?.sleep_count ?? 0
	};
}

/**
 * Every kind of record a provider sent, so the bar answers "where does the data
 * come from" rather than "where do data points come from".
 */
export const providerParts = (
	providers: ProviderDataCount[],
	labelFor: (provider: string) => string
) =>
	providers
		.map((entry) => ({
			key: entry.provider,
			label: labelFor(entry.provider),
			value: entry.data_points + entry.workout_count + entry.sleep_count
		}))
		.sort((a, b) => b.value - a.value);

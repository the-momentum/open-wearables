import type { Coverage } from './types';

export const LAYERS = {
	timeseries: 'Time series',
	workout: 'Workout fields',
	sleep: 'Sleep fields',
	cycle: 'Cycle fields',
	score: 'Health scores'
} as const;

export type Layer = keyof typeof LAYERS;

/**
 * One shape for every layer of the matrix. The response splits them by the table
 * they land in, which is a backend concern — to a reader they are all "a thing a
 * provider can send".
 */
export type Capability = {
	code: string;
	layer: Layer;
	/** The timeseries category, or the layer's own name where it has none. */
	group: string;
	unit?: string;
	description?: string;
	providers: string[];
};

export function capabilities(coverage: Coverage): Capability[] {
	const fields = (layer: Layer, rows: { code: string; providers: string[] }[]) =>
		rows.map((row) => ({ ...row, layer, group: LAYERS[layer] }));

	return [
		...coverage.timeseries.flatMap((category) =>
			category.metrics.map((metric) => ({
				...metric,
				layer: 'timeseries' as Layer,
				group: category.name
			}))
		),
		...fields('workout', coverage.workout_fields),
		...fields('sleep', coverage.sleep_fields),
		...fields('cycle', coverage.menstrual_cycle_fields),
		...fields('score', coverage.health_scores)
	];
}

export type Filters = { search: string; layer: Layer | ''; provider: string; missing: boolean };

/** `missing` inverts the provider filter: what it *cannot* send. */
export function filterCapabilities(rows: Capability[], filters: Filters): Capability[] {
	const term = filters.search.trim().toLowerCase();

	return rows.filter((row) => {
		if (filters.layer && row.layer !== filters.layer) return false;
		if (term && !row.code.toLowerCase().includes(term)) return false;
		if (!filters.provider) return true;
		return row.providers.includes(filters.provider) !== filters.missing;
	});
}

/** How many of the whole matrix each provider covers, richest first. */
export function providerTotals(rows: Capability[]): Record<string, number> {
	const counts = new Map<string, number>();
	for (const row of rows) {
		for (const provider of row.providers) counts.set(provider, (counts.get(provider) ?? 0) + 1);
	}
	return Object.fromEntries([...counts.entries()].sort(([, a], [, b]) => b - a));
}

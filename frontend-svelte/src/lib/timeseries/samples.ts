import { humanise } from '$lib/utils/text';

/** Mirrors backend `TimeSeriesSample`. */
export type Sample = {
	timestamp: string;
	type: string;
	value: number;
	unit: string;
	source: { provider: string; device: string | null; device_name: string | null } | null;
	is_daily_total: boolean | null;
};

export type Series = {
	type: string;
	unit: string;
	/** Names the device only when a type arrives from more than one. */
	label: string;
	device: string | null;
	points: { at: number; value: number }[];
};

/** What a workout's own sensors record, in the order the chart stacks them. */
export const WORKOUT_TYPES = ['heart_rate', 'power', 'cadence', 'speed'];

/** What a whole day records: movement and effort rather than a single session. */
export const ACTIVITY_TYPES = ['steps', 'energy', 'heart_rate'];

const HOUR = 3_600_000;

/**
 * Coarse enough that one request covers the workout. The endpoint caps a page
 * at 1000 samples, and a silently truncated curve is worse than a coarser one.
 */
export function resolutionFor(seconds: number): '1min' | '5min' | '15min' {
	const hours = (seconds * 1000) / HOUR;
	if (hours <= 12) return '1min';
	return hours <= 60 ? '5min' : '15min';
}

/**
 * One line per type **and device**. The API aggregates one row per (bucket,
 * data source, series type), so two watches worn the same hour arrive
 * interleaved under one type; merging them by timestamp draws a saw between two
 * devices instead of either one's curve.
 *
 * Daily totals share this endpoint in raw mode and would tower over every real
 * reading, so they go — the flag is tri-state and a legacy null means "not a
 * total".
 */
export function toSeries(samples: Sample[], order: string[] = WORKOUT_TYPES): Series[] {
	const groups = new Map<string, Series>();

	for (const sample of samples) {
		if (sample.is_daily_total === true) continue;

		const device = sample.source?.device_name ?? sample.source?.device ?? null;
		const key = `${sample.type}::${device ?? ''}`;
		const series = groups.get(key) ?? {
			type: sample.type,
			unit: sample.unit,
			label: humanise(sample.type),
			device,
			points: []
		};
		series.points.push({ at: new Date(sample.timestamp).getTime(), value: sample.value });
		groups.set(key, series);
	}

	const kept = [...groups.values()].filter((series) => series.points.length > 1);
	for (const series of kept) series.points.sort((a, b) => a.at - b.at);

	// Only say which device when it disambiguates; otherwise the legend is noise.
	for (const series of kept) {
		const sameType = kept.filter((other) => other.type === series.type);
		if (sameType.length > 1 && series.device) series.label = `${series.label} · ${series.device}`;
	}

	const rank = (type: string) => order.indexOf(type);
	return kept.sort((a, b) => rank(a.type) - rank(b.type));
}

/** Theme tokens, so a chart line cannot drift from the rest of the palette. */
const SERIES_COLOUR: Record<string, string> = {
	heart_rate: 'var(--color-danger)',
	power: 'var(--color-warning)',
	energy: 'var(--color-warning)',
	cadence: 'var(--color-primary)',
	steps: 'var(--color-primary)',
	speed: 'var(--color-success)'
};

export const seriesColour = (type: string) => SERIES_COLOUR[type] ?? 'var(--color-primary)';

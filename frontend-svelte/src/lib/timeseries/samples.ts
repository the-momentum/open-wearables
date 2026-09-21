import type { Line } from '$lib/charts/geometry';
import { collect } from '$lib/utils/collect';
import { humanise } from '$lib/utils/text';
import { dailyPoints } from './daily';

/** Mirrors backend `TimeSeriesSample`. */
export type Sample = {
	timestamp: string;
	type: string;
	value: number;
	unit: string;
	source: { provider: string; device: string | null; device_name: string | null } | null;
	is_daily_total: boolean | null;
};

/** A drawn line that came from a device, which is what may need naming. */
export type Series = Line & {
	/** Named in the label only when a type arrives from more than one. */
	device: string | null;
};

/** What a workout's own sensors record, in the order the chart stacks them. */
export const WORKOUT_TYPES = ['heart_rate', 'power', 'cadence', 'speed'];

/** What a whole day records: movement and effort rather than a single session. */
export const ACTIVITY_TYPES = ['steps', 'energy', 'heart_rate'];

/**
 * Vitals worth a trend rather than a reading. Each is plotted on its own, since
 * a body-fat percentage and a resting pulse share no axis.
 */
export const VITAL_TYPES = [
	'resting_heart_rate',
	'heart_rate_variability_rmssd',
	'oxygen_saturation',
	'respiratory_rate',
	'vo2_max',
	'weight',
	'body_fat_percentage'
];

const HOUR = 3_600_000;

/**
 * Coarse enough that one request covers the window. The endpoint caps a page at
 * 1000 samples, and a silently truncated curve is worse than a coarser one.
 */
export function resolutionFor(seconds: number): '1min' | '5min' | '15min' | '1hour' {
	const hours = (seconds * 1000) / HOUR;
	if (hours <= 12) return '1min';
	if (hours <= 60) return '5min';
	// Past ten days even quarter-hours overrun a page, and a body trend is read by
	// the day anyway.
	return hours <= 240 ? '15min' : '1hour';
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
	const deviceOf = (sample: Sample) => sample.source?.device_name ?? sample.source?.device ?? null;

	const readings = samples.filter((sample) => sample.is_daily_total !== true);
	const groups = collect(readings, (sample) => `${sample.type}::${deviceOf(sample) ?? ''}`);

	const kept = [...groups.values()]
		.map((group) => ({
			type: group[0].type,
			unit: group[0].unit,
			label: humanise(group[0].type),
			device: deviceOf(group[0]),
			points: group
				.map((sample) => ({ at: new Date(sample.timestamp).getTime(), value: sample.value }))
				.sort((a, b) => a.at - b.at)
		}))
		// One reading draws no line, and a lone dot says less than a figure.
		.filter((series) => series.points.length > 1);

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
	resting_heart_rate: 'var(--color-danger)',
	power: 'var(--color-warning)',
	energy: 'var(--color-warning)',
	weight: 'var(--color-warning)',
	cadence: 'var(--color-primary)',
	steps: 'var(--color-primary)',
	heart_rate_variability_rmssd: 'var(--color-primary)',
	speed: 'var(--color-success)',
	oxygen_saturation: 'var(--color-success)',
	respiratory_rate: 'var(--color-success)',
	vo2_max: 'var(--color-primary)'
};

export const seriesColour = (type: string) => SERIES_COLOUR[type] ?? 'var(--color-primary)';

/**
 * One point a day. The endpoint has no daily rollup to ask for, so a dense
 * series like HRV would otherwise arrive thousands of points deep, overrun a
 * page, and be silently cut.
 */
export const dailyMeans = (series: Series): Series => ({
	...series,
	points: dailyPoints(
		series.points.map((point) => ({
			day: new Date(point.at).toISOString().slice(0, 10),
			value: point.value
		}))
	)
});

/**
 * The backend names units for machines (`percent`, `ml_kg_min`); this is what a
 * reader expects to see. A leading space, or none where the symbol hugs its
 * number.
 */
const UNIT_LABEL: Record<string, string> = {
	percent: '%',
	ml_kg_min: ' ml/kg/min',
	m_per_s: ' m/s',
	kg_m2: '',
	count: ''
};

export const unitLabel = (unit: string) => UNIT_LABEL[unit] ?? ` ${unit}`;

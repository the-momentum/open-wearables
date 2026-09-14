import type { DataTimeline, TimelineSeries } from './types';
import { weekStart } from './period';

export type Cell = { date: string; count: number };
export type Row = { key: string; cells: Cell[]; total: number };

const DAY_MS = 86_400_000;

const iso = (date: Date) => date.toISOString().slice(0, 10);

const step = (date: Date, bucket: 'day' | 'week') =>
	new Date(date.getTime() + (bucket === 'week' ? 7 : 1) * DAY_MS);

/**
 * Every bucket in the window, so a gap is a visible cell. `align` only applies
 * to a window the caller chose: API dates are already on the backend's boundary
 * and snapping them again shifts every key so nothing matches.
 */
function grid(from: Date, to: Date, bucket: 'day' | 'week', align: boolean): string[] {
	const dates: string[] = [];
	for (
		let at = align && bucket === 'week' ? weekStart(from) : from;
		at < to;
		at = step(at, bucket)
	) {
		dates.push(iso(at));
	}
	return dates;
}

/** Widest span any series covers, when the caller bounded nothing. */
function span(series: TimelineSeries[], bucket: 'day' | 'week'): { from: Date; to: Date } | null {
	const dates = series.flatMap((entry) => entry.buckets.map(([date]) => date)).sort();
	if (dates.length === 0) return null;

	const last = new Date(`${dates[dates.length - 1]}T00:00:00Z`);
	// Half-open, so the final bucket is inside the grid.
	return { from: new Date(`${dates[0]}T00:00:00Z`), to: step(last, bucket) };
}

export function toRows(
	timeline: DataTimeline,
	window: { from: Date; to: Date } | null
): { rows: Row[]; dates: string[]; max: number } {
	const bounds = window ?? span(timeline.series, timeline.bucket);
	if (!bounds) return { rows: [], dates: [], max: 0 };

	const dates = grid(bounds.from, bounds.to, timeline.bucket, window !== null);

	const rows = timeline.series.map((entry) => {
		const counts = new Map(entry.buckets);
		const cells = dates.map((date) => ({ date, count: counts.get(date) ?? 0 }));
		return { key: entry.key, cells, total: cells.reduce((sum, cell) => sum + cell.count, 0) };
	});

	const max = Math.max(0, ...rows.flatMap((row) => row.cells.map((cell) => cell.count)));
	rows.sort((a, b) => b.total - a.total);

	return { rows, dates, max };
}

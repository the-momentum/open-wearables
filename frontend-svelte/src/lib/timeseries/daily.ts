import type { Point } from '$lib/charts/geometry';
import { collect } from '$lib/utils/collect';

/**
 * One point a day, the mean of that day's readings, anchored at midday.
 *
 * Midday matters: a daily point drawn at midnight sits at the boundary between
 * the two days it could belong to, and two charts anchoring differently would
 * show the same day half a day apart.
 */
export function dailyPoints(readings: { day: string; value: number }[]): Point[] {
	return [...collect(readings, (reading) => reading.day).entries()]
		.sort(([a], [b]) => a.localeCompare(b))
		.map(([day, own]) => ({
			at: new Date(`${day}T12:00:00Z`).getTime(),
			value: own.reduce((sum, reading) => sum + reading.value, 0) / own.length
		}));
}

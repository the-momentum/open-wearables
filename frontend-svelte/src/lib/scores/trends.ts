import { spanOf, type Line } from '$lib/charts/geometry';
import { dailyPoints } from '$lib/timeseries/daily';
import { collect } from '$lib/utils/collect';
import { localDayKey } from '$lib/utils/format';
import { byCategory, knownCategory, providerOf, scoreOf } from './categories';
import type { HealthScore } from './types';

export type CategoryTrend = {
	category: string;
	/** One line per provider, a point a day. */
	lines: Line[];
	/** One range for every provider, never one each: their scales differ. */
	range: { low: number; high: number };
	latest: { provider: string; label: string; value: number }[];
	days: number;
};

/**
 * A point a day per provider. They sample at their own rhythm — one score a
 * night, or one every half hour — and a trend across weeks is read by the day.
 */
function providerLines(scores: HealthScore[], labelFor: (provider: string) => string): Line[] {
	const scored = scores
		.map((score) => ({ score, value: scoreOf(score) }))
		.filter((entry): entry is { score: HealthScore; value: number } => entry.value !== null);

	return [...collect(scored, (entry) => providerOf(entry.score)).entries()]
		.map(([provider, own]) => ({
			type: provider,
			label: labelFor(provider),
			unit: '',
			points: dailyPoints(
				own.map((entry) => ({
					day: localDayKey(entry.score.recorded_at, entry.score.zone_offset),
					value: entry.value
				}))
			)
		}))
		.sort((a, b) => a.type.localeCompare(b.type));
}

export function categoryTrends(
	scores: HealthScore[],
	labelFor: (provider: string) => string
): CategoryTrend[] {
	return (
		[...collect(scores, (score) => score.category).entries()]
			.map(([category, own]) => {
				const lines = providerLines(own, labelFor);

				return {
					category,
					lines,
					range: spanOf(lines),
					latest: lines.map((line) => ({
						provider: line.type,
						label: line.label,
						value: line.points[line.points.length - 1].value
					})),
					days: new Set(lines.flatMap((line) => line.points.map((point) => point.at))).size
				};
			})
			// A category nobody scored has no line, and no range to draw one against.
			.filter((trend) => trend.lines.length > 0)
			.sort((a, b) => byCategory(a.category, b.category))
	);
}

/**
 * Every provider that scored anything, in one fixed order. The palette assigns
 * by position, so without a single order Suunto is the third colour in a tile
 * and the first inside a card.
 */
export const providersIn = (trends: CategoryTrend[]): string[] =>
	[...new Set(trends.flatMap((trend) => trend.lines.map((line) => line.type)))].sort();

/**
 * The categories there is anything to choose between. `chosen` stays on the
 * list while the trends that name the others are still in flight, so the
 * control never contradicts the page it is on.
 */
export const categoriesIn = (trends: CategoryTrend[], chosen: string): string[] =>
	[...new Set([...trends.map((trend) => trend.category), ...(chosen ? [chosen] : [])])]
		.filter(knownCategory)
		.sort(byCategory);

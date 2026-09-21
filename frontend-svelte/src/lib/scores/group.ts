import { collect } from '$lib/utils/collect';
import { localDayKey } from '$lib/utils/format';
import { byCategory, providerOf, scoreOf } from './categories';
import type { HealthScore } from './types';

export type ProviderReading = {
	provider: string;
	/** The reading itself, or the mean where a provider sampled all day. */
	score: number | null;
	/** The rating, or the one that held for most of the day. */
	qualifier: string | null;
	readings: number;
	/** Only where a mean stands in for several, which is the span it hides. */
	spread: { low: number; high: number } | null;
	/** Newest first: the components come off the first of these. */
	all: HealthScore[];
};

/** One measure on one day, and everyone who scored it. */
export type CategoryScores = { category: string; providers: ProviderReading[] };

export type DayScores = {
	day: string;
	/** Whatever a reading was stored against, for the heading's own clock. */
	recordedAt: string;
	zoneOffset: string | null;
	/** Everyone who scored anything that day, for the card's header. */
	providers: string[];
	categories: CategoryScores[];
};

/** The rating that held for most of the readings, which is the day's character. */
function dominant(readings: HealthScore[]): string | null {
	const counts = new Map<string, number>();
	for (const reading of readings) {
		if (reading.qualifier) counts.set(reading.qualifier, (counts.get(reading.qualifier) ?? 0) + 1);
	}

	let best: string | null = null;
	for (const [qualifier, count] of counts) {
		if (best === null || count > counts.get(best)!) best = qualifier;
	}
	return best;
}

function reduceProvider(provider: string, readings: HealthScore[]): ProviderReading {
	const scores = readings.map(scoreOf).filter((score): score is number => score !== null);
	const mean = scores.length ? scores.reduce((sum, score) => sum + score, 0) / scores.length : null;

	return {
		provider,
		score: mean,
		qualifier: dominant(readings),
		readings: readings.length,
		spread: scores.length > 1 ? { low: Math.min(...scores), high: Math.max(...scores) } : null,
		all: readings
	};
}

/**
 * A card is a day, and inside it a row per measure. A provider that sampled all
 * day collapses to that day's mean — which is read off the number of readings,
 * never off a list of providers known to stream.
 */
export function groupByDay(scores: HealthScore[]): DayScores[] {
	const days = collect(scores, (score) => localDayKey(score.recorded_at, score.zone_offset));

	return [...days.entries()]
		.map(([day, readings]) => ({
			day,
			recordedAt: readings[0].recorded_at,
			zoneOffset: readings[0].zone_offset,
			providers: [...new Set(readings.map(providerOf))].sort(),
			// Sorted, not left in the order they arrived: the records come back
			// interleaved by time, so first appearance says nothing.
			categories: [...collect(readings, (reading) => reading.category).entries()]
				.map(([category, own]) => ({
					category,
					providers: [...collect(own, providerOf).entries()]
						.map(([provider, mine]) => reduceProvider(provider, mine))
						.sort((a, b) => a.provider.localeCompare(b.provider))
				}))
				.sort((a, b) => byCategory(a.category, b.category))
		}))
		.sort((a, b) => b.day.localeCompare(a.day));
}

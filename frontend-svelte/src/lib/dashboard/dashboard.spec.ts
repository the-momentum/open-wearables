import { describe, expect, it } from 'vitest';
import { formatCompact, formatPercent, formatShare } from '$lib/utils/format';
import { coverageOf, eventMix, providerUse, statTiles } from './stats';
import type { SystemInfo } from './types';

const info = (over: Partial<SystemInfo> = {}): SystemInfo => ({
	total_users: { count: 1200 },
	active_conn: { count: 900 },
	data_points: { count: 1_450_000, archived: 320_000 },
	event_records: { count: 1000, workouts: 400, sleep: 560, menstrual_cycles: 40 },
	connections_coverage: {
		users_with_active: 900,
		users_with_multi_active: 180,
		top_providers: [
			{ provider: 'garmin', count: 500 },
			{ provider: 'oura', count: 300 }
		]
	},
	...over
});

describe('formatCompact', () => {
	// The tiles carry counts that reach seven digits, and one of them is an
	// estimate — a compact figure fits the tile and does not overclaim.
	it.each([
		[7, '7'],
		[999, '999'],
		[8432, '8.4K'],
		[51_420, '51.4K'],
		[1_450_000, '1.5M'],
		[2_300_000_000, '2.3B']
	])('renders %i as %s', (value, expected) => {
		expect(formatCompact(value)).toBe(expected);
	});

	// It rolls at the boundary rather than spelling "1000K".
	it('carries K into M at the boundary', () => {
		expect(formatCompact(999_499)).toBe('999.5K');
		expect(formatCompact(999_999)).toBe('1M');
	});

	it('has a dash for a count that is not there', () => {
		expect(formatCompact(null)).toBe('—');
	});
});

describe('coverageOf', () => {
	it('splits the user base into connected and not', () => {
		expect(coverageOf(info())).toEqual({
			connected: 900,
			unconnected: 300,
			percent: 75,
			multi: 180,
			multiPercent: 15
		});
	});

	// A fresh install has no users, and a percentage of nothing is zero, not NaN.
	it('survives an empty platform', () => {
		const empty = coverageOf(
			info({
				total_users: { count: 0 },
				connections_coverage: {
					users_with_active: 0,
					users_with_multi_active: 0,
					top_providers: []
				}
			})
		);
		expect([empty.percent, empty.multiPercent, empty.unconnected]).toEqual([0, 0, 0]);
	});

	// The two counts come from different queries, so nothing guarantees the
	// ordering a subtraction assumes.
	it('never reports a negative remainder', () => {
		const odd = coverageOf(info({ total_users: { count: 10 } }));
		expect(odd.unconnected).toBe(0);
	});
});

describe('eventMix', () => {
	it('leaves out a category nothing was recorded in', () => {
		const mix = eventMix(
			info({ event_records: { count: 960, workouts: 400, sleep: 560, menstrual_cycles: 0 } })
		);
		expect(mix).toEqual({ workouts: 400, sleep: 560 });
	});

	// `count` is every category and only three have a field of their own, so the
	// rest is named rather than leaving the parts short of the whole.
	it('names whatever the three known categories do not account for', () => {
		const mix = eventMix(
			info({ event_records: { count: 1200, workouts: 400, sleep: 560, menstrual_cycles: 40 } })
		);
		expect(mix.other).toBe(200);
	});
});

describe('providerUse', () => {
	it('keeps the ranking the backend already made', () => {
		expect(Object.entries(providerUse(info()))).toEqual([
			['garmin', 500],
			['oura', 300]
		]);
	});
});

describe('formatShare', () => {
	// Written twice before this existed, once with toFixed and once with round.
	it('pairs a count with what share of the whole it is', () => {
		expect(formatShare(480, 902)).toBe('480 · 53%');
		expect(formatShare(11_766, 20_418)).toBe('11,766 · 58%');
	});

	it('calls it zero rather than dividing by one', () => {
		expect(formatShare(0, 0)).toBe('0 · 0%');
	});

	// 57 KB of archive in a 475 MB database rounded to "0%", which read as empty.
	it('never calls something present zero', () => {
		expect(formatPercent(57, 475_000)).toBe('<1%');
		expect(formatPercent(0, 475_000)).toBe('0%');
		expect(formatShare(3, 1000)).toBe('3 · <1%');
	});
});

describe('statTiles', () => {
	it('spells out the cheap counts and compacts the aggregates', () => {
		const [users, , points] = statTiles(info());
		expect(users.value).toBe('1,200');
		expect(points.value).toBe('1.5M');
		// The response never says which figures are estimates, so the one that can
		// be says so itself.
		expect(points.note).toBe('estimated');
	});

	// The archive row is the one that disappeared when an empty part was left out
	// of a proportion bar; every tile keeps its sub-metrics whatever they read.
	it('keeps a zero sub-metric', () => {
		const [, , points] = statTiles(info({ data_points: { count: 10, archived: 0 } }));
		expect(points.parts).toEqual([{ label: 'archived', value: '0' }]);
	});
});

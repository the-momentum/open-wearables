import { describe, expect, it } from 'vitest';
import { localDayKey } from '$lib/utils/format';
import { byCategory, componentsOf, knownCategory, rawReading, scoreOf } from './categories';
import { detailSections, hasDetail } from './details';
import { groupByDay } from './group';
import { dayCount, dayPages, dayWindow } from './paging';
import { categoriesIn } from './trends';
import { categoryTrends } from './trends';
import type { HealthScore } from './types';

const score = (over: Partial<HealthScore> = {}): HealthScore => ({
	id: crypto.randomUUID(),
	category: 'sleep',
	provider: 'oura',
	value: 88,
	qualifier: null,
	recorded_at: '2026-09-18T00:00:00Z',
	zone_offset: null,
	components: null,
	event_record_id: null,
	...over
});

/** As the resilience task stores it: the CV in `value`, the score beside it. */
const resilience = (cv: number, points: number) =>
	score({
		category: 'resilience',
		provider: 'internal',
		value: cv,
		components: {
			metric_type: { value: null, qualifier: 'RMSSD' },
			days_counted: { value: 5, qualifier: null },
			resilience_score: { value: points, qualifier: null }
		}
	});

const label = (provider: string) => provider.toUpperCase();

describe('scoreOf', () => {
	it('reads the score straight off value for an ordinary category', () => {
		expect(scoreOf(score({ value: 73 }))).toBe(73);
	});

	// `value` on a resilience row is the HRV coefficient of variation, not a
	// score: 0.157 shown as a resilience score is off by a factor of five hundred.
	it('takes resilience from its component, not from value', () => {
		expect(scoreOf(resilience(0.157, 74))).toBe(74);
	});

	it('has no score when the component it lives in is missing', () => {
		expect(scoreOf(score({ category: 'resilience', value: 0.157 }))).toBeNull();
	});
});

describe('rawReading', () => {
	it('gives the resilience value a name and a scale of its own', () => {
		expect(rawReading(resilience(0.157, 74))).toEqual({
			label: 'HRV variability',
			value: '15.7%'
		});
	});

	// Everywhere else `value` is the score the card already shows, so repeating
	// it under another heading would be inventing a second reading.
	it('is nothing where value is the score itself', () => {
		expect(rawReading(score())).toBeNull();
	});
});

describe('componentsOf', () => {
	it('drops the component the card is already showing as the score', () => {
		const labels = componentsOf(resilience(0.157, 74)).map((field) => field.label);
		expect(labels).not.toContain('Resilience score');
		expect(labels).toContain('Days counted');
	});

	it('keeps a rating that came with no number of its own', () => {
		const fields = componentsOf(resilience(0.157, 74));
		expect(fields).toContainEqual({ label: 'Metric type', value: 'RMSSD' });
	});

	it('shows a number and its rating together', () => {
		const fields = componentsOf(
			score({ components: { stress_state: { value: 2, qualifier: 'Active' } } })
		);
		expect(fields).toEqual([{ label: 'Stress state', value: '2 · Active' }]);
	});
});

describe('groupByDay', () => {
	it('puts a day on one card, with a row per measure', () => {
		const days = groupByDay([
			score({ category: 'readiness', recorded_at: '2026-09-18T00:00:00Z' }),
			score({ category: 'sleep', recorded_at: '2026-09-18T00:00:00Z' })
		]);

		expect(days).toHaveLength(1);
		// Sleep before readiness however they arrived: the records come back
		// interleaved by time, so first appearance is noise.
		expect(days[0].categories.map((row) => row.category)).toEqual(['sleep', 'readiness']);
	});

	it('puts every provider for one measure in the same row', () => {
		const days = groupByDay([
			score({ provider: 'oura', value: 88 }),
			score({ provider: 'internal', value: 83 })
		]);

		const [sleep] = days[0].categories;
		expect(sleep.providers.map((entry) => entry.provider)).toEqual(['internal', 'oura']);
		expect(sleep.providers.map((entry) => entry.score)).toEqual([83, 88]);
		// And the header names them once for the whole day, not once per row.
		expect(days[0].providers).toEqual(['internal', 'oura']);
	});

	it('orders the days newest first', () => {
		const days = groupByDay([
			score({ recorded_at: '2026-09-17T00:00:00Z' }),
			score({ recorded_at: '2026-09-19T00:00:00Z' }),
			score({ recorded_at: '2026-09-18T00:00:00Z' })
		]);

		expect(days.map((entry) => entry.day)).toEqual(['2026-09-19', '2026-09-18', '2026-09-17']);
	});

	// Suunto's stress-recovery stream arrives every half hour, so a day of it is
	// thirty-five rows. One row showing the mean, with the span it hides.
	it('collapses a provider that sampled all day to a mean and a spread', () => {
		const stream = [40, 50, 60].map((value, index) =>
			score({
				category: 'recovery',
				provider: 'suunto',
				value,
				recorded_at: `2026-09-19T0${index}:00:00Z`
			})
		);

		const [reading] = groupByDay(stream)[0].categories[0].providers;
		expect(reading.score).toBe(50);
		expect(reading.spread).toEqual({ low: 40, high: 60 });
		expect(reading.readings).toBe(3);
	});

	it('leaves a single reading without a spread to explain', () => {
		expect(groupByDay([score()])[0].categories[0].providers[0].spread).toBeNull();
	});

	it('names the rating that held for most of the day', () => {
		const stream = ['Relaxing', 'Active', 'Relaxing'].map((qualifier, index) =>
			score({ provider: 'suunto', qualifier, recorded_at: `2026-09-19T0${index}:00:00Z` })
		);

		expect(groupByDay(stream)[0].categories[0].providers[0].qualifier).toBe('Relaxing');
	});

	it('keeps the readings newest first, which is what the components describe', () => {
		const days = groupByDay([
			score({ value: 90, recorded_at: '2026-09-18T09:00:00Z' }),
			score({ value: 80, recorded_at: '2026-09-18T08:00:00Z' })
		]);

		expect(days[0].categories[0].providers[0].all[0].value).toBe(90);
	});
});

describe('categoryTrends', () => {
	it('draws a line per provider, a point a day', () => {
		const trends = categoryTrends(
			[
				score({ provider: 'oura', value: 88, recorded_at: '2026-09-18T00:00:00Z' }),
				score({ provider: 'oura', value: 80, recorded_at: '2026-09-17T00:00:00Z' }),
				score({ provider: 'internal', value: 70, recorded_at: '2026-09-18T00:00:00Z' })
			],
			label
		);

		expect(trends).toHaveLength(1);
		expect(trends[0].lines.map((line) => [line.type, line.points.length])).toEqual([
			['internal', 1],
			['oura', 2]
		]);
	});

	it('averages a day that was scored many times into its one point', () => {
		const trends = categoryTrends(
			[
				score({ provider: 'suunto', value: 40, recorded_at: '2026-09-19T01:00:00Z' }),
				score({ provider: 'suunto', value: 60, recorded_at: '2026-09-19T02:00:00Z' })
			],
			label
		);

		expect(trends[0].lines[0].points).toEqual([
			{ at: new Date('2026-09-19T12:00:00Z').getTime(), value: 50 }
		]);
	});

	/**
	 * Readiness is 1-100 from Oura and 0-10 from Polar. Scaled apart, a 6 out of
	 * 10 draws level with a 93 out of 100 — which is the comparison this tab
	 * exists to make, drawn backwards.
	 */
	it('spans every provider in the category with one range', () => {
		const trends = categoryTrends(
			[
				score({ category: 'readiness', provider: 'oura', value: 93 }),
				score({ category: 'readiness', provider: 'polar', value: 6 })
			],
			label
		);

		expect(trends[0].range).toEqual({ low: 6, high: 93 });
	});

	it('leaves out a category nothing in the period scored', () => {
		const trends = categoryTrends([score({ category: 'stress', value: null })], label);
		expect(trends).toEqual([]);
	});

	it('reports what each provider last said', () => {
		const trends = categoryTrends(
			[
				score({ value: 88, recorded_at: '2026-09-18T00:00:00Z' }),
				score({ value: 62, recorded_at: '2026-09-10T00:00:00Z' })
			],
			label
		);

		expect(trends[0].latest).toEqual([{ provider: 'oura', label: 'OURA', value: 88 }]);
	});
});

describe('byCategory', () => {
	it('keeps the known categories in their own order', () => {
		expect(['strain', 'sleep', 'readiness'].sort(byCategory)).toEqual([
			'sleep',
			'readiness',
			'strain'
		]);
	});

	// A category the backend grows later still renders; it just sorts after the
	// ones this build knows about rather than jumping the queue.
	it('puts one it has never heard of last', () => {
		expect(['zzz_new', 'sleep'].sort(byCategory)).toEqual(['sleep', 'zzz_new']);
		expect(knownCategory('zzz_new')).toBe(false);
	});
});

describe('localDayKey', () => {
	it('groups by the day the reading fell on in its own zone', () => {
		expect(localDayKey('2026-09-18T23:30:00Z', '-07:00')).toBe('2026-09-18');
		// The same instant is already the next day in Warsaw, and a score belongs
		// to the day its owner lived, not to ours.
		expect(localDayKey('2026-09-18T23:30:00Z', '+02:00')).toBe('2026-09-19');
	});

	it('falls back to UTC, which is all a row without an offset can say', () => {
		expect(localDayKey('2026-09-18T23:30:00Z', null)).toBe('2026-09-18');
	});
});

describe('dayWindow', () => {
	// A ninety-day period, ten days to a page.
	const period = { from: new Date('2026-06-24T00:00:00Z'), to: new Date('2026-09-22T00:00:00Z') };

	it('counts the period in days and pages', () => {
		expect(dayCount(period)).toBe(90);
		expect(dayPages(period, 10)).toBe(9);
	});

	// Page one is the newest stretch, which is where an admin opening the tab is
	// looking — not the oldest, the way an ascending list would start.
	it('starts page one at the newest days', () => {
		expect(dayWindow(period, 1, 10)).toEqual({
			from: new Date('2026-09-12T00:00:00Z'),
			to: new Date('2026-09-22T00:00:00Z')
		});
	});

	it('walks back a page at a time', () => {
		expect(dayWindow(period, 2, 10).to).toEqual(new Date('2026-09-12T00:00:00Z'));
		expect(dayWindow(period, 9, 10).from).toEqual(period.from);
	});

	// 95 days at ten to a page leaves five on the last one, and that window must
	// stop at the start of the period rather than running past it.
	it('clips the last page to what is left of the period', () => {
		const odd = { from: new Date('2026-06-19T00:00:00Z'), to: period.to };
		expect(dayPages(odd, 10)).toBe(10);
		expect(dayWindow(odd, 10, 10)).toEqual({
			from: odd.from,
			to: new Date('2026-06-24T00:00:00Z')
		});
	});
});

describe('detailSections', () => {
	const sectionsOf = (scores: HealthScore[]) =>
		detailSections(groupByDay(scores)[0].categories, label);

	// A provider with one score has a number and nothing to plot; the curve is
	// what a provider that sampled through the day earned.
	it('draws a curve only for a provider that sampled through the day', () => {
		const single = sectionsOf([score({ value: 88 })]);
		expect(single[0].lines).toEqual([]);

		const stream = sectionsOf(
			[40, 60].map((value, index) =>
				score({ provider: 'suunto', value, recorded_at: `2026-09-19T0${index}:00:00Z` })
			)
		);
		expect(stream[0].lines[0].points).toHaveLength(2);
	});

	it('gives every provider a column of its own components', () => {
		const sections = sectionsOf([
			score({ provider: 'oura', components: { timing: { value: 99, qualifier: null } } }),
			score({ provider: 'internal', components: { stages: { value: 80, qualifier: null } } })
		]);

		expect(sections[0].groups.map((group) => group.title)).toEqual(['INTERNAL', 'OURA']);
	});

	// Nothing to draw and nothing to list, so the section is not rendered at all
	// rather than opening onto an empty frame.
	it('has no detail where a provider sent a bare score', () => {
		expect(sectionsOf([score({ components: null })]).filter(hasDetail)).toEqual([]);
	});
});

describe('categoriesIn', () => {
	const trends = [{ category: 'sleep' }, { category: 'readiness' }] as Parameters<
		typeof categoriesIn
	>[0];

	it('offers what the period holds, in their own order', () => {
		expect(categoriesIn(trends, '')).toEqual(['sleep', 'readiness']);
	});

	// The trends are fetched by the browser, so the chosen one has to stay on the
	// list while they are in flight — or the control contradicts the page it is on.
	it('keeps the chosen category while the trends are still in flight', () => {
		expect(categoriesIn([], 'recovery')).toEqual(['recovery']);
	});

	it('leaves out one the API cannot be asked to filter by', () => {
		expect(categoriesIn([], 'invented')).toEqual([]);
	});
});

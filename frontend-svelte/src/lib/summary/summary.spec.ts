import { describe, expect, it } from 'vitest';
import { ALL_TIME, parsePeriod, periodBucket, periodWindow, spanDays, weekStart } from './period';
import { narrowToProvider } from './narrow';
import { toRows } from './timeline';
import type { DataTimeline } from './types';

const params = (query: string) => new URLSearchParams(query);

describe('parsePeriod', () => {
	it('reads no bounds as the whole history', () => {
		expect(parsePeriod(params(''))).toEqual(ALL_TIME);
	});

	it('calls equal bounds a day and different ones a range', () => {
		expect(parsePeriod(params('from=2026-09-01&to=2026-09-01')).mode).toBe('day');
		expect(parsePeriod(params('from=2026-09-01&to=2026-09-30')).mode).toBe('range');
	});

	it('treats one bound as that single day', () => {
		expect(parsePeriod(params('from=2026-09-01'))).toEqual({
			mode: 'day',
			from: '2026-09-01',
			to: '2026-09-01'
		});
	});

	it('sorts an inverted pair rather than asking for nothing', () => {
		expect(parsePeriod(params('from=2026-09-30&to=2026-09-01'))).toEqual({
			mode: 'range',
			from: '2026-09-01',
			to: '2026-09-30'
		});
	});

	it('ignores a query string that is not a date', () => {
		expect(parsePeriod(params('from=yesterday&to=soon'))).toEqual(ALL_TIME);
	});
});

describe('periodWindow', () => {
	// Half-open, or the last day of a range would be missing from the counts.
	it('ends the day after the last one asked for', () => {
		const window = periodWindow({ mode: 'range', from: '2026-09-01', to: '2026-09-02' });
		expect(window?.to.toISOString().slice(0, 10)).toBe('2026-09-03');
		expect(spanDays({ mode: 'range', from: '2026-09-01', to: '2026-09-02' })).toBe(2);
	});

	it('is null for the whole history, which has no bounds to send', () => {
		expect(periodWindow(ALL_TIME)).toBeNull();
	});
});

describe('periodBucket', () => {
	it('switches to weeks once daily cells stop fitting', () => {
		expect(periodBucket({ mode: 'range', from: '2026-06-13', to: '2026-09-10' })).toBe('day');
		expect(periodBucket({ mode: 'range', from: '2025-09-10', to: '2026-09-10' })).toBe('week');
		expect(periodBucket(ALL_TIME)).toBe('week');
	});
});

describe('weekStart', () => {
	// Postgres date_trunc('week') is Monday-based, so the grid must be too.
	it.each([
		['2026-09-10', '2026-09-07'],
		['2026-09-07', '2026-09-07'],
		['2026-09-06', '2026-08-31']
	])('snaps %s back to %s', (day, expected) => {
		expect(
			weekStart(new Date(`${day}T12:00:00Z`))
				.toISOString()
				.slice(0, 10)
		).toBe(expected);
	});
});

const timeline = (series: DataTimeline['series']): DataTimeline => ({
	bucket: 'day',
	group_by: 'provider',
	series
});

describe('toRows', () => {
	const window = {
		from: new Date('2026-09-01T00:00:00Z'),
		to: new Date('2026-09-05T00:00:00Z')
	};

	it('fills the gaps the sparse response leaves out', () => {
		const { rows, dates } = toRows(
			timeline([{ key: 'oura', metric: 'data_points', buckets: [['2026-09-03', 5]] }]),
			window
		);

		expect(dates).toEqual(['2026-09-01', '2026-09-02', '2026-09-03', '2026-09-04']);
		expect(rows[0].cells.map((cell) => cell.count)).toEqual([0, 0, 5, 0]);
	});

	it('puts the busiest provider first, since the others are read against it', () => {
		const { rows, max } = toRows(
			timeline([
				{ key: 'quiet', metric: 'data_points', buckets: [['2026-09-01', 2]] },
				{ key: 'busy', metric: 'data_points', buckets: [['2026-09-02', 90]] }
			]),
			window
		);

		expect(rows.map((row) => row.key)).toEqual(['busy', 'quiet']);
		expect(max).toBe(90);
	});

	it('derives its own span when no window was asked for', () => {
		const { dates } = toRows(
			timeline([
				{
					key: 'oura',
					metric: 'data_points',
					buckets: [
						['2026-09-01', 1],
						['2026-09-03', 1]
					]
				}
			]),
			null
		);

		expect(dates).toEqual(['2026-09-01', '2026-09-02', '2026-09-03']);
	});
});

describe('toRows over the whole history', () => {
	// The bug this covers: aligning a derived span to Monday shifted every key,
	// so an all-time weekly view rendered every count as zero.
	it("keeps the API's own bucket dates when no window was asked for", () => {
		const { rows, dates } = toRows(
			{
				bucket: 'week',
				group_by: 'provider',
				series: [
					{
						key: 'oura',
						metric: 'data_points',
						buckets: [
							['2026-08-31', 10],
							['2026-09-14', 30]
						]
					}
				]
			},
			null
		);

		expect(dates).toEqual(['2026-08-31', '2026-09-07', '2026-09-14']);
		expect(rows[0].cells.map((cell) => cell.count)).toEqual([10, 0, 30]);
		expect(rows[0].total).toBe(40);
	});
});

describe('narrowToProvider', () => {
	const summary = {
		total_data_points: 100,
		total_workouts: 9,
		total_sleep_events: 7,
		series_type_counts: { heart_rate: 90, steps: 10 },
		workout_type_counts: { running: 9 },
		by_provider: [
			{
				provider: 'oura',
				data_points: 40,
				series_counts: { heart_rate: 40 },
				workout_count: 2,
				sleep_count: 3
			}
		],
		has_womens_health_data: false
	};

	it("takes the provider's own counts, not the page totals", () => {
		const narrowed = narrowToProvider(summary, 'oura');
		expect(narrowed.total_data_points).toBe(40);
		expect(narrowed.total_workouts).toBe(2);
		expect(narrowed.series_type_counts).toEqual({ heart_rate: 40 });
	});

	// Absent from by_provider means it delivered nothing in this period; showing
	// everyone's totals under its name would be a lie.
	it('is zeroes for a provider that delivered nothing', () => {
		const narrowed = narrowToProvider(summary, 'garmin');
		expect(narrowed.total_data_points).toBe(0);
		expect(narrowed.series_type_counts).toEqual({});
	});
});

import { describe, expect, it } from 'vitest';
import { extent, linePath, scaleY } from '$lib/charts/geometry';
import { dailyMeans, resolutionFor, toSeries, unitLabel, type Sample } from './samples';

describe('dailyMeans', () => {
	const series = {
		type: 'heart_rate_variability_rmssd',
		unit: 'ms',
		label: 'HRV',
		device: null,
		points: [
			{ at: Date.parse('2026-09-20T02:00:00Z'), value: 40 },
			{ at: Date.parse('2026-09-20T22:00:00Z'), value: 50 },
			{ at: Date.parse('2026-09-21T03:00:00Z'), value: 60 }
		]
	};

	// HRV arrives dozens of times a day. Left alone it overruns a page and gets
	// silently cut; a body trend is read by the day anyway.
	it('collapses a day of readings into their mean', () => {
		expect(dailyMeans(series).points.map((point) => point.value)).toEqual([45, 60]);
	});

	it('orders the days it produces, whatever order they arrived in', () => {
		const shuffled = { ...series, points: [...series.points].reverse() };
		const days = dailyMeans(shuffled).points.map((point) =>
			new Date(point.at).toISOString().slice(0, 10)
		);
		expect(days).toEqual(['2026-09-20', '2026-09-21']);
	});
});

describe('resolutionFor', () => {
	// A month of quarter-hours is three thousand buckets, which the endpoint caps
	// at a thousand — so a long window has to ask for hours.
	it('coarsens as the window grows', () => {
		expect(resolutionFor(3600)).toBe('1min');
		expect(resolutionFor(86_400 * 2)).toBe('5min');
		expect(resolutionFor(86_400 * 8)).toBe('15min');
		expect(resolutionFor(86_400 * 90)).toBe('1hour');
	});
});

describe('unitLabel', () => {
	it('shows a symbol where there is one and a spaced word where there is not', () => {
		expect(unitLabel('percent')).toBe('%');
		expect(unitLabel('bpm')).toBe(' bpm');
		expect(unitLabel('ml_kg_min')).toBe(' ml/kg/min');
	});
});

describe('linePath', () => {
	const box = { width: 100, height: 50, pad: 5 };
	const window = { from: 0, to: 100 };

	// Both charts draw through this, so a drift here would show as two charts
	// disagreeing about where a value sits.
	it('maps time to width and value to its own range', () => {
		const points = [
			{ at: 0, value: 10 },
			{ at: 50, value: 20 },
			{ at: 100, value: 30 }
		];
		expect(linePath(points, window, extent(points), box)).toBe('M0.0 45.0 L50.0 25.0 L100.0 5.0');
	});

	// A flat series has no range to spread across, and dividing by it would put
	// the line at infinity.
	it('centres a series that never changed', () => {
		const flat = [
			{ at: 0, value: 7 },
			{ at: 100, value: 7 }
		];
		expect(linePath(flat, window, extent(flat), box)).toBe('M0.0 25.0 L100.0 25.0');
	});

	it('leaves room at the top and bottom, so a peak is not clipped', () => {
		const y = scaleY(0, 10, box);
		expect([y(10), y(0)]).toEqual([box.pad, box.height - box.pad]);
	});
});

describe('toSeries', () => {
	const sample = (over: Partial<Sample>): Sample => ({
		timestamp: '2026-09-20T08:00:00Z',
		type: 'heart_rate',
		value: 100,
		unit: 'bpm',
		source: null,
		is_daily_total: false,
		...over
	});

	// Raw mode returns intraday readings and daily totals in one stream, and a
	// day's total towering over per-minute readings destroys the axis.
	it('drops the daily totals sharing the stream', () => {
		const series = toSeries([
			sample({ value: 60 }),
			sample({ timestamp: '2026-09-20T09:00:00Z', value: 65 }),
			sample({ value: 9000, is_daily_total: true })
		]);
		expect(series[0].points.map((point) => point.value)).toEqual([60, 65]);
	});

	// The API returns one row per bucket *per source*, so merging by timestamp
	// draws a saw between two devices instead of either one's curve.
	it('keeps two devices apart and names them', () => {
		const watch = { provider: 'garmin', device: 'FR265', device_name: 'Forerunner 265' };
		const ring = { provider: 'oura', device: 'Gen3', device_name: 'Oura Ring' };
		const series = toSeries([
			sample({ source: watch }),
			sample({ timestamp: '2026-09-20T09:00:00Z', source: watch }),
			sample({ source: ring }),
			sample({ timestamp: '2026-09-20T09:00:00Z', source: ring })
		]);

		expect(series.map((entry) => entry.label)).toEqual([
			'Heart rate · Forerunner 265',
			'Heart rate · Oura Ring'
		]);
	});

	// One point draws no line, so a lone reading is not a series.
	it('leaves out a type with a single reading', () => {
		expect(toSeries([sample({})])).toEqual([]);
	});
});

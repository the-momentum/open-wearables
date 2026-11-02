import { describe, expect, it } from 'vitest';
import { formatBytes } from '$lib/utils/format';
import {
	DAYS_PER_MONTH,
	dailyIngest,
	fromFields,
	growthOf,
	invalid,
	policyOf,
	project,
	PROJECTION_MONTHS,
	ROLLUP_RATIO,
	ROLLUP_RATIO_LABEL,
	samePolicy,
	settingsOf,
	toFields
} from './projection';
import type { StorageEstimate } from './types';

const MB = 1024 ** 2;

const storage = (over: Partial<StorageEstimate> = {}): StorageEstimate => ({
	live_data_bytes: 300 * MB,
	live_index_bytes: 100 * MB,
	aggregate_data_bytes: 2 * MB,
	aggregate_index_bytes: 1 * MB,
	other_tables_bytes: 50 * MB,
	total_bytes: 453 * MB,
	live_row_count: 1_000_000,
	aggregate_row_count: 4_000,
	live_data_span_days: 200,
	...over
});

const monthly = (policy: { rollup: boolean; retain: number | null }) =>
	project(storage(), policy).map((point) => point.bytes);

describe('project', () => {
	it('draws one point a month, today included', () => {
		const points = project(storage(), { rollup: true, retain: null });
		expect(points).toHaveLength(PROJECTION_MONTHS + 1);
		expect(points[0]).toEqual({ month: 0, bytes: 403 * MB });
	});

	it('stays flat when there is nothing live to grow from', () => {
		const points = project(storage({ live_row_count: 0 }), { rollup: true, retain: 30 });
		expect(new Set(points.map((point) => point.bytes)).size).toBe(1);
	});

	// The shape is the point of the chart: each policy is one of the three growth classes.
	it('levels off with deletion and no rollup', () => {
		const bounded = monthly({ rollup: false, retain: 30 });
		expect(bounded.at(-1)).toBe(bounded.at(-2));
	});

	it('keeps growing slowly with deletion and rollup: the rolled-up days stay', () => {
		const efficient = monthly({ rollup: true, retain: 30 });
		const perMonth = dailyIngest(storage()) * ROLLUP_RATIO * DAYS_PER_MONTH;
		expect(efficient.at(-1)! - efficient.at(-2)!).toBeCloseTo(perMonth, -1);
	});

	it('grows with every sample without deletion', () => {
		const linear = monthly({ rollup: false, retain: null });
		expect(linear.at(-1)! - linear.at(-2)!).toBeCloseTo(
			dailyIngest(storage()) * DAYS_PER_MONTH,
			-1
		);
	});
});

describe('policy', () => {
	it('names the growth class the way the backend does', () => {
		expect(growthOf({ rollup: true, retain: null })).toBe('linear');
		expect(growthOf({ rollup: false, retain: null })).toBe('linear');
		expect(growthOf({ rollup: true, retain: 365 })).toBe('linear_efficient');
		expect(growthOf({ rollup: false, retain: 365 })).toBe('bounded');
	});

	// The PUT rejects these with a 422 whose detail is a list, which the
	// reader would see as nothing - so the form says it first.
	it('refuses what the API would', () => {
		expect(invalid({ rollup: true, retain: 0 })).toMatch(/1 to 7300/);
		expect(invalid({ rollup: true, retain: 1.5 })).toMatch(/whole number/);
		expect(invalid({ rollup: false, retain: 7301 })).toMatch(/1 to 7300/);
		expect(invalid({ rollup: true, retain: 365 })).toBeNull();
		expect(invalid({ rollup: false, retain: null })).toBeNull();
	});

	it('estimates the daily ingest off the span the live data covers', () => {
		expect(dailyIngest(storage())).toBe((400 * MB) / 200);
		expect(dailyIngest(storage({ live_row_count: 0 }))).toBe(0);
	});
});

describe('the policy on the wire', () => {
	// The save bar encodes, the action decodes: both halves live in one module,
	// and this is what holds them to each other.
	it('survives the trip through a form', () => {
		for (const policy of [
			{ rollup: true, retain: 365 },
			{ rollup: false, retain: 90 },
			{ rollup: false, retain: null }
		]) {
			const form = new FormData();
			for (const [name, value] of Object.entries(toFields(policy))) form.set(name, value);
			expect(fromFields(form)).toEqual(policy);
		}
	});

	it('maps onto the names the API uses, and back', () => {
		const policy = { rollup: true, retain: 365 };
		expect(settingsOf(policy)).toEqual({ rollup_enabled: true, delete_after_days: 365 });
		expect(policyOf(settingsOf(policy))).toEqual(policy);
	});

	it('tells a real change from none', () => {
		expect(samePolicy({ rollup: true, retain: null }, { rollup: true, retain: null })).toBe(true);
		expect(samePolicy({ rollup: true, retain: null }, { rollup: false, retain: null })).toBe(false);
		expect(samePolicy({ rollup: true, retain: 30 }, { rollup: true, retain: 31 })).toBe(false);
	});

	it('says the ratio the maths uses', () => {
		expect(ROLLUP_RATIO_LABEL).toBe('1/500');
	});
});

describe('formatBytes', () => {
	// Base 1024 and the backend's unit names, so the two never disagree.
	it('reads the way the API does', () => {
		expect(formatBytes(0)).toBe('0 B');
		expect(formatBytes(512)).toBe('512 B');
		expect(formatBytes(1536)).toBe('1.5 KB');
		expect(formatBytes(459 * MB)).toBe('459.0 MB');
		expect(formatBytes(3.2 * 1024 ** 3)).toBe('3.2 GB');
	});
});

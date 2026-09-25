import { describe, expect, it } from 'vitest';
import { detailGroups } from './fields';
import { sumActivity } from './totals';
import type { ActivityDay } from './types';

const day = (over: Partial<ActivityDay>) =>
	({
		date: '2026-09-20',
		steps: 8000,
		distance_meters: 5760,
		active_calories_kcal: 336,
		total_calories_kcal: 1986,
		active_minutes: 52,
		sedentary_minutes: 580,
		floors_climbed: null,
		elevation_meters: null,
		intensity_minutes: null,
		heart_rate: null,
		...over
	}) as ActivityDay;

describe('sumActivity', () => {
	// A day with no steps is a gap in the data, not a day someone spent still —
	// averaging it as zero would drag the figure down for the days that do count.
	it('averages steps over the days that reported them', () => {
		const totals = sumActivity(
			[day({ steps: 10_000 }), day({ steps: null }), day({ steps: 6000 })],
			3,
			false
		);
		expect([totals.steps, totals.averageSteps]).toEqual([16_000, 8000]);
	});

	it('has no average when nobody reported steps', () => {
		expect(sumActivity([day({ steps: null })], 1, false).averageSteps).toBeNull();
	});

	// This endpoint returns no count at all, so `has_more` is the only honest
	// signal that the sums are short.
	it('flags itself partial from has_more, with no count to compare', () => {
		expect(sumActivity([day({})], null, true).partial).toBe(true);
		expect(sumActivity([day({})], null, false).partial).toBe(false);
	});
});

describe('detailGroups', () => {
	it('drops a group the provider had nothing for', () => {
		const titles = detailGroups(day({})).map((group) => group.title);
		expect(titles).toContain('Movement');
		// Oura reports no intensity bands and this day has no elevation, so neither
		// heading appears — but energy does, because the total arrived.
		expect(titles).not.toContain('Intensity');
		expect(titles).not.toContain('Elevation');
		expect(titles).toContain('Energy');
	});

	it('reads minutes as durations, not as bare numbers', () => {
		const movement = detailGroups(day({ active_minutes: 95 }))[0];
		expect(movement.fields[0]).toEqual({ label: 'Active', value: '1h 35m' });
	});

	// Zero floors climbed is a reading; a missing one is not.
	it('keeps a zero and drops a null', () => {
		const titles = (over: Partial<ActivityDay>) =>
			detailGroups(day(over))
				.flatMap((group) => group.fields)
				.map((field) => field.label);
		expect(titles({ floors_climbed: 0 })).toContain('Floors');
		expect(titles({ floors_climbed: null })).not.toContain('Floors');
	});
});

import { describe, expect, it } from 'vitest';
import { detailGroups } from './fields';
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

describe('detailGroups', () => {
	it('drops a group the provider had nothing for', () => {
		const titles = detailGroups(day({})).map((group) => group.title);
		expect(titles).toContain('Movement');
		// Oura reports no intensity bands and this day has no elevation, so neither
		// heading appears - but energy does, because the total arrived.
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

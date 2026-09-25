import { describe, expect, it } from 'vitest';
import Activity from '@lucide/svelte/icons/activity';
import Bike from '@lucide/svelte/icons/bike';
import CircleDot from '@lucide/svelte/icons/circle-dot';
import Cpu from '@lucide/svelte/icons/cpu';
import Mountain from '@lucide/svelte/icons/mountain';
import Smartphone from '@lucide/svelte/icons/smartphone';
import Watch from '@lucide/svelte/icons/watch';
import {
	DASH,
	formatDistance,
	formatDuration,
	formatLocalDay,
	formatLocalTime,
	formatNumber,
	formatPace
} from '$lib/utils/format';
import { workoutIcon } from './kinds';
import { zoneKinds } from './zones';
import type { Workout } from './types';
import { deviceIcon } from '$lib/providers/devices';

describe('formatDuration', () => {
	it('carries hours only once there are some', () => {
		expect(formatDuration(2880)).toBe('48m');
		expect(formatDuration(5520)).toBe('1h 32m');
		expect(formatDuration(3600)).toBe('1h 0m');
	});

	// Zero seconds is a provider that sent the field empty, not a workout of no
	// length, and "0m" would read as a measurement.
	it('is a dash for nothing and for zero', () => {
		expect(formatDuration(null)).toBe(DASH);
		expect(formatDuration(0)).toBe(DASH);
	});
});

describe('formatDistance', () => {
	it('switches to kilometres at a kilometre', () => {
		expect(formatDistance(8200)).toBe('8.20 km');
		expect(formatDistance(1000)).toBe('1.00 km');
		expect(formatDistance(840)).toBe('840 m');
	});

	it('is a dash for a workout that covers no ground', () => {
		expect(formatDistance(null)).toBe(DASH);
		expect(formatDistance(0)).toBe(DASH);
	});
});

describe('formatPace', () => {
	it('reads as minutes and seconds per kilometre', () => {
		expect(formatPace(351)).toBe('5:51 /km');
		expect(formatPace(300)).toBe('5:00 /km');
		// Padded, so 4:05 does not come out as 4:5.
		expect(formatPace(245)).toBe('4:05 /km');
	});
});

describe('formatNumber', () => {
	it('keeps zero, which is a reading', () => {
		expect(formatNumber(0, ' kcal')).toBe('0 kcal');
		expect(formatNumber(null, ' kcal')).toBe(DASH);
	});
});

describe('formatLocalTime', () => {
	const morning = '2026-09-15T07:12:00Z';

	// The offset is the workout's own, so a run at 09:12 in Warsaw must not read
	// as 07:12 because the admin — or the CI box — sits in UTC.
	it('shows the clock the workout was recorded against', () => {
		expect(formatLocalTime(morning, '+02:00')).toBe('09:12');
		expect(formatLocalTime(morning, '-05:30')).toBe('01:42');
	});

	// Saying UTC out loud matters most for a user abroad: an unmarked 07:12 reads
	// as their morning when it is only the instant we stored.
	it('marks the fallback when the provider never sent an offset', () => {
		expect(formatLocalTime(morning, null)).toBe('07:12 UTC');
	});

	it('carries the shift across midnight into the day as well', () => {
		expect(formatLocalDay('2026-09-15T23:30:00Z', '+02:00')).toBe('Wed, 16 Sept 2026');
		expect(formatLocalDay('2026-09-15T00:30:00Z', '-05:30')).toBe('Mon, 14 Sept 2026');
	});
});

describe('deviceIcon', () => {
	it('tells the kinds of device apart', () => {
		expect(deviceIcon('watch')).toBe(Watch);
		expect(deviceIcon('ring')).toBe(CircleDot);
		expect(deviceIcon('phone')).toBe(Smartphone);
	});

	// `unknown` and `other` are real DeviceType members, and a null arrives
	// whenever the provider named no device at all.
	it('falls back rather than guessing a shape', () => {
		expect(deviceIcon('unknown')).toBe(Cpu);
		expect(deviceIcon(null)).toBe(Cpu);
	});
});

describe('workoutIcon', () => {
	// Both patterns match `mountain_biking`; the order of the table is what
	// decides, and getting it wrong is silent.
	it('reads a compound slug as the sport, not the terrain', () => {
		expect(workoutIcon('mountain_biking')).toBe(Bike);
		expect(workoutIcon('mountaineering')).toBe(Mountain);
	});

	it('gives an unknown type the generic mark rather than nothing', () => {
		expect(workoutIcon('underwater_basket_weaving')).toBe(Activity);
		expect(workoutIcon('other')).toBe(Activity);
	});
});

describe('zoneKinds', () => {
	const workout = (hr: boolean, power: boolean) =>
		({
			hr_zones: hr ? { zones: [{ zone: 0, seconds: 60, max_bpm: 120 }], max_hr: 190 } : null,
			power_zones: power ? { zones: [{ zone: 0, seconds: 60, max_watts: 150 }] } : null
		}) as Workout;

	// Both shapes name their ceiling differently, and everything downstream — the
	// bands, the ranges in the strip — reads one `max`.
	it('flattens either ceiling to the same field', () => {
		expect(zoneKinds(workout(true, true)).map((kind) => [kind.type, kind.zones[0].max])).toEqual([
			['heart_rate', 120],
			['power', 150]
		]);
	});

	it('offers only what the provider sent', () => {
		expect(zoneKinds(workout(true, false)).map((kind) => kind.type)).toEqual(['heart_rate']);
		expect(zoneKinds(workout(false, false))).toEqual([]);
	});
});

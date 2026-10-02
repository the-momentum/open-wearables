import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import type { Coverage } from '$lib/coverage/types';
import { humanise } from '$lib/utils/text';
import { countsOf } from './summary';
import { SEED_PROVIDERS, WORKOUT_BOUND, WORKOUT_TYPE_GROUPS, seriesGroups } from './catalogue';
import {
	datesFor,
	draftFrom,
	matchingPreset,
	problems,
	profileOf,
	requestOf,
	type Draft
} from './draft';
import type { SeedPreset, SeedProfile } from './types';

const repo = (path: string) => readFileSync(resolve(process.cwd(), '..', path), 'utf8');

/** Shaped like the backend's presets: months, no dates, providers left to chance. */
const profile = (over: Partial<SeedProfile> = {}): SeedProfile => ({
	preset: null,
	generate_workouts: true,
	generate_sleep: true,
	generate_time_series: true,
	providers: null,
	num_connections: 2,
	workout_config: {
		count: 80,
		workout_types: null,
		duration_min_minutes: 15,
		duration_max_minutes: 180,
		hr_min_range: [90, 120],
		hr_max_range: [140, 180],
		steps_range: [500, 20000],
		date_range_months: 6,
		date_from: null,
		date_to: null
	},
	sleep_config: {
		count: 20,
		duration_min_minutes: 300,
		duration_max_minutes: 600,
		nap_chance_pct: 10,
		weekend_catchup: false,
		date_range_months: 6,
		date_from: null,
		date_to: null,
		stage_profile: null,
		stage_distribution: {
			deep_pct_range: [15, 25],
			rem_pct_range: [20, 25],
			awake_pct_range: [2, 8]
		}
	},
	time_series_config: {
		enabled_types: ['heart_rate', 'steps', 'cadence'],
		include_blood_pressure: false,
		date_range_months: 6,
		date_from: null,
		date_to: null
	},
	...over
});

const preset = (id: string, over: Partial<SeedProfile> = {}): SeedPreset => ({
	id,
	label: id,
	description: '',
	profile: profile({ preset: id, ...over })
});

const draft = (over: Partial<SeedProfile> = {}): Draft =>
	draftFrom(profile(over), { users: 1, seed: null });

describe('what the catalogue claims about the backend', () => {
	// No endpoint lists these, so each is held to the file the backend reads.
	it('offers exactly the providers the generator has device profiles for', () => {
		const source = repo('backend/app/services/seed_data/constants.py');
		const table = source.slice(
			source.indexOf('PROVIDER_CONFIGS'),
			source.indexOf('SEED_PROVIDERS')
		);
		const names = [...table.matchAll(/ProviderName\.([A-Z_]+):/g)].map((match) =>
			match[1].toLowerCase()
		);
		expect([...SEED_PROVIDERS].sort()).toEqual(names.sort());
	});

	it('marks exactly the series the generator only emits inside workouts', () => {
		const config = repo('backend/scripts/init/series_type_config.yaml');
		const bound = [...config.matchAll(/^ {2}([a-z0-9_]+):\n\s+cadence: workout_bound/gm)].map(
			(match) => match[1]
		);
		expect([...WORKOUT_BOUND].sort()).toEqual(bound.sort());
	});

	it('names only workout types the API still has', () => {
		const spec = JSON.parse(repo('docs/openapi.json'));
		const known = new Set<string>(spec.components.schemas.WorkoutType.enum);
		const unknown = WORKOUT_TYPE_GROUPS.flatMap((group) => group.types).filter(
			(type) => !known.has(type)
		);
		expect(unknown).toEqual([]);
	});
});

describe('draft and profile', () => {
	// What a preset says has to come back out unchanged, or picking one and
	// generating would not generate that preset.
	it('round-trips a preset', () => {
		const original = profile({ providers: ['garmin', 'oura'] });
		expect(profileOf(draftFrom(original, { users: 1, seed: null }), null)).toEqual(original);
	});

	it('sets the connection count from the providers picked', () => {
		const picked = { ...draft(), providers: ['garmin', 'oura', 'polar'], connections: 1 };
		// The backend keeps providers[:num_connections]; a count of one would
		// quietly drop two of the three.
		expect(profileOf(picked, null)).toMatchObject({
			providers: ['garmin', 'oura', 'polar'],
			num_connections: 3
		});
	});

	it('applies one window to all three kinds of data', () => {
		const custom = { ...draft(), window: { from: '2026-01-01', to: '2026-03-31' } };
		const out = profileOf(custom, null);
		for (const config of [out.workout_config, out.sleep_config, out.time_series_config]) {
			expect(config).toMatchObject({ date_from: '2026-01-01', date_to: '2026-03-31' });
		}
	});

	it('sends no seed when it is left empty, so the backend picks one', () => {
		expect(requestOf(draft(), null).random_seed).toBeNull();
		expect(requestOf({ ...draft(), seed: 42 }, null).random_seed).toBe(42);
	});
});

describe('matchingPreset', () => {
	const presets = [preset('minimal', {}), preset('big', { num_connections: 5 })];

	it('recognises an untouched preset', () => {
		expect(matchingPreset(draft(), presets)).toBe('minimal');
		expect(matchingPreset(draft({ num_connections: 5 }), presets)).toBe('big');
	});

	it('lets go as soon as a field differs, and picks it up again when it is put back', () => {
		const edited = draft();
		edited.workouts.count = 81;
		expect(matchingPreset(edited, presets)).toBeNull();
		edited.workouts.count = 80;
		expect(matchingPreset(edited, presets)).toBe('minimal');
	});

	// Chips switched on in a different order ask for the same thing.
	it('does not care what order the series were picked in', () => {
		const reordered = draft();
		reordered.series.types = ['cadence', 'steps', 'heart_rate'];
		expect(matchingPreset(reordered, presets)).toBe('minimal');
	});
});

describe('problems', () => {
	it('passes a preset as it is', () => {
		expect(problems(draft())).toEqual([]);
	});

	it('refuses what the API would, in words', () => {
		const bad = draft();
		bad.users = 11;
		bad.workouts.duration = [200, 100];
		bad.sleep.napChance = 101;
		expect(problems(bad)).toEqual([
			'Users must be 1 to 10.',
			'Workout length must run low to high, within 5 to 600 minutes.',
			'Nap chance must be 0 to 100%.'
		]);
	});

	it('asks for something to generate', () => {
		const empty = draft({
			generate_workouts: false,
			generate_sleep: false,
			generate_time_series: false
		});
		expect(problems(empty)).toContain('Turn on at least one kind of data.');
	});

	it('only checks stage shares when no named profile is chosen', () => {
		const custom = draft();
		custom.sleep.deep = [60, 70];
		custom.sleep.rem = [50, 60];
		expect(problems(custom)).toContain(
			'The lowest stage shares add up to more than a whole night.'
		);
		custom.sleep.stageProfile = 'optimal';
		expect(problems(custom)).toEqual([]);
	});

	it('caps the providers at the connections a user can have', () => {
		expect(problems({ ...draft(), providers: [...SEED_PROVIDERS] })).toContain(
			'Pick at most 5 providers.'
		);
	});
});

describe('seriesGroups', () => {
	const coverage = {
		timeseries: [
			{ name: 'Heart & Cardiovascular', metrics: [{ code: 'heart_rate' }, { code: 'vo2_max' }] },
			{ name: 'Activity - Basic', metrics: [{ code: 'steps' }] },
			{ name: 'Activity - Running', metrics: [{ code: 'running_speed' }] },
			{ name: 'Activity - Generic', metrics: [{ code: 'cadence' }] }
		]
	} as unknown as Coverage;

	it('offers only what some preset asks for, grouped the way coverage groups it', () => {
		const groups = seriesGroups([preset('a')], coverage);
		expect(groups).toEqual([
			{ label: 'Heart & Cardiovascular', types: ['heart_rate'] },
			{ label: 'Activity', types: ['steps'] },
			// Set apart: with workouts off they produce nothing.
			{ label: 'During workouts', types: ['cadence'] }
		]);
	});
});

describe('datesFor', () => {
	it('turns a month count into the dates it covers', () => {
		expect(datesFor(6, new Date('2026-09-23T12:00:00Z'))).toEqual({
			from: '2026-03-23',
			to: '2026-09-23'
		});
	});
});

describe('series names', () => {
	// humanise already knows the acronyms; a second helper for series was written and removed.
	it('reads the way a person would write them', () => {
		expect(humanise('heart_rate_variability_sdnn')).toBe('Heart rate variability SDNN');
		expect(humanise('vo2_max')).toBe('VO2 max');
	});
});

describe('countsOf', () => {
	// The preset tiles and the line above the button read from this one place.
	it('names only what the profile generates', () => {
		expect(countsOf(profile())).toEqual(['80 workouts', '20 nights', '3 series types']);
		expect(countsOf(profile({ generate_sleep: false }))).toEqual(['80 workouts', '3 series types']);
	});
});

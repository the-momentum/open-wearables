import type { Coverage } from '$lib/coverage/types';
import { grouped } from '$lib/utils/collect';
import type { SeedPreset } from './types';

/** The ones the generator can fake (backend `PROVIDER_CONFIGS`); no endpoint lists them, a test does. */
export const SEED_PROVIDERS = ['apple', 'garmin', 'oura', 'polar', 'suunto', 'whoop'];

/** The API's ceiling on connections per user, and so on providers picked. */
export const MAX_CONNECTIONS = 5;

/** Emitted only inside workouts — `cadence: workout_bound` in the generator's config, held to it by a test. */
export const WORKOUT_BOUND = [
	'running_power',
	'running_speed',
	'cadence',
	'power',
	'swimming_stroke_count'
];

/**
 * The old dashboard's grouping; the API has none. Niche types are left out —
 * "any type" still draws from all of them — and a test checks each name exists.
 */
export const WORKOUT_TYPE_GROUPS: { label: string; types: string[] }[] = [
	{
		label: 'Running & walking',
		types: ['running', 'trail_running', 'treadmill', 'walking', 'hiking', 'mountaineering']
	},
	{ label: 'Cycling', types: ['cycling', 'indoor_cycling', 'mountain_biking', 'e_biking'] },
	{
		label: 'Water',
		types: ['swimming', 'pool_swimming', 'open_water_swimming', 'rowing', 'kayaking', 'surfing']
	},
	{
		label: 'Gym',
		types: [
			'strength_training',
			'cardio_training',
			'elliptical',
			'rowing_machine',
			'stair_climbing'
		]
	},
	{ label: 'Mind & body', types: ['yoga', 'pilates', 'stretching', 'meditation'] },
	{
		label: 'Winter',
		types: ['cross_country_skiing', 'alpine_skiing', 'snowboarding', 'ice_skating']
	},
	{
		label: 'Team & racket',
		types: ['soccer', 'basketball', 'volleyball', 'hockey', 'tennis', 'badminton', 'padel']
	},
	{ label: 'Combat & climbing', types: ['boxing', 'martial_arts', 'rock_climbing', 'bouldering'] },
	{ label: 'Other', types: ['triathlon', 'dance', 'golf', 'skating'] }
];

export type SeriesGroup = { label: string; types: string[] };

/**
 * What the presets ask for is what the generator can emit, so no list here
 * can fall behind it. Grouped as coverage groups them, "Activity - X" folded
 * into one, with the workout-bound ones apart.
 */
export function seriesGroups(presets: SeedPreset[], coverage: Coverage): SeriesGroup[] {
	const asked = presets.flatMap((preset) => preset.profile.time_series_config.enabled_types);
	const seedable = new Set(asked.filter((type) => !WORKOUT_BOUND.includes(type)));

	const placed = coverage.timeseries.flatMap((group) =>
		group.metrics
			.filter((metric) => seedable.has(metric.code))
			.map((metric) => ({ label: group.name.split(' - ')[0], type: metric.code }))
	);
	const known = new Set(placed.map((entry) => entry.type));
	const stray = [...seedable]
		.filter((type) => !known.has(type))
		.sort()
		.map((type) => ({ label: 'Other', type }));

	const groups = grouped([...placed, ...stray], (entry) => entry.label).map((group) => ({
		label: group.key,
		types: group.items.map((entry) => entry.type)
	}));

	const bound = WORKOUT_BOUND.filter((type) => asked.includes(type));
	return bound.length > 0 ? [...groups, { label: 'During workouts', types: bound }] : groups;
}

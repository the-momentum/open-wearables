import { MAX_CONNECTIONS } from './catalogue';
import type { Range, SeedPreset, SeedProfile, SeedRequest, SleepProfile } from './types';
import { isoDay } from '$lib/utils/datetime';
import { isWholeIn } from '$lib/utils/numbers';

/** One window for all three kinds of data: every preset uses the same one. */
export type Window = { months: number } | { from: string; to: string };

export type Draft = {
	users: number;
	/** Null lets the backend pick one. */
	seed: number | null;
	window: Window;
	/** Empty picks at random, `connections` of them. */
	providers: string[];
	connections: number;
	workouts: {
		on: boolean;
		count: number;
		/** Null draws from every type. */
		types: string[] | null;
		duration: Range;
		hrMin: Range;
		hrMax: Range;
		steps: Range;
	};
	sleep: {
		on: boolean;
		count: number;
		duration: Range;
		napChance: number;
		weekendCatchup: boolean;
		/** A named profile, or null for the ranges below. */
		stageProfile: string | null;
		deep: Range;
		rem: Range;
		awake: Range;
	};
	series: { on: boolean; types: string[]; bloodPressure: boolean };
};

export const LIMITS = {
	users: [1, 10],
	connections: [1, MAX_CONNECTIONS],
	months: [1, 24],
	workouts: [0, 500],
	workoutMinutes: [5, 600],
	nights: [0, 365],
	sleepMinutes: [60, 720],
	percent: [0, 100]
} as const;

export const WINDOW_MONTHS = [1, 3, 6, 12, 24];

/** What "the last N months" means as dates, so switching to dates starts there. */
export function datesFor(months: number, now = new Date()): { from: string; to: string } {
	const from = new Date(now);
	from.setUTCMonth(from.getUTCMonth() - months);
	return { from: isoDay(from), to: isoDay(now) };
}

export function draftFrom(profile: SeedProfile, keep: Pick<Draft, 'users' | 'seed'>): Draft {
	const { workout_config: w, sleep_config: s, time_series_config: t } = profile;

	return {
		...keep,
		window:
			w.date_from && w.date_to
				? { from: w.date_from, to: w.date_to }
				: { months: w.date_range_months },
		providers: profile.providers ?? [],
		connections: profile.num_connections,
		workouts: {
			on: profile.generate_workouts,
			count: w.count,
			types: w.workout_types,
			duration: [w.duration_min_minutes, w.duration_max_minutes],
			hrMin: [...w.hr_min_range],
			hrMax: [...w.hr_max_range],
			steps: [...w.steps_range]
		},
		sleep: {
			on: profile.generate_sleep,
			count: s.count,
			duration: [s.duration_min_minutes, s.duration_max_minutes],
			napChance: s.nap_chance_pct,
			weekendCatchup: s.weekend_catchup,
			stageProfile: s.stage_profile,
			deep: [...s.stage_distribution.deep_pct_range],
			rem: [...s.stage_distribution.rem_pct_range],
			awake: [...s.stage_distribution.awake_pct_range]
		},
		series: {
			on: profile.generate_time_series,
			types: [...t.enabled_types],
			bloodPressure: t.include_blood_pressure
		}
	};
}

const windowFields = (window: Window) =>
	'months' in window
		? { date_range_months: window.months, date_from: null, date_to: null }
		: { date_range_months: LIMITS.months[1], date_from: window.from, date_to: window.to };

/**
 * Picked providers set the connection count themselves: the backend keeps
 * `providers[:num_connections]`, so picking four with a count of two would
 * quietly drop the last two.
 */
export function profileOf(draft: Draft, preset: string | null): SeedProfile {
	const window = windowFields(draft.window);
	const picked = draft.providers.length > 0;

	return {
		preset,
		generate_workouts: draft.workouts.on,
		generate_sleep: draft.sleep.on,
		generate_time_series: draft.series.on,
		providers: picked ? [...draft.providers] : null,
		num_connections: picked ? draft.providers.length : draft.connections,
		workout_config: {
			count: draft.workouts.count,
			workout_types: draft.workouts.types,
			duration_min_minutes: draft.workouts.duration[0],
			duration_max_minutes: draft.workouts.duration[1],
			hr_min_range: draft.workouts.hrMin,
			hr_max_range: draft.workouts.hrMax,
			steps_range: draft.workouts.steps,
			...window
		},
		sleep_config: {
			count: draft.sleep.count,
			duration_min_minutes: draft.sleep.duration[0],
			duration_max_minutes: draft.sleep.duration[1],
			nap_chance_pct: draft.sleep.napChance,
			weekend_catchup: draft.sleep.weekendCatchup,
			stage_profile: draft.sleep.stageProfile,
			stage_distribution: {
				deep_pct_range: draft.sleep.deep,
				rem_pct_range: draft.sleep.rem,
				awake_pct_range: draft.sleep.awake
			},
			...window
		},
		time_series_config: {
			enabled_types: [...draft.series.types],
			include_blood_pressure: draft.series.bloodPressure,
			...window
		}
	};
}

export const requestOf = (draft: Draft, preset: string | null): SeedRequest => ({
	num_users: draft.users,
	profile: profileOf(draft, preset),
	random_seed: draft.seed
});

/**
 * One string per meaning. Keys are sorted at every level — the backend's field
 * order is not this module's, and `JSON.stringify` minds — and a list of names
 * is sorted too, since chips switched on in another order ask for the same thing.
 */
const canonical = (value: unknown) =>
	JSON.stringify(value, (_, item) => {
		if (Array.isArray(item)) {
			return item.every((entry) => typeof entry === 'string') ? [...item].sort() : item;
		}
		if (item && typeof item === 'object') {
			return Object.fromEntries(Object.entries(item).sort(([a], [b]) => a.localeCompare(b)));
		}
		return item;
	});

/**
 * The preset the draft still is, if any. Derived rather than remembered, so
 * editing a field back to what the preset had selects it again.
 */
export function matchingPreset(draft: Draft, presets: SeedPreset[]): string | null {
	const key = (profile: SeedProfile) => canonical({ ...normalise(profile), preset: null });

	const mine = key(profileOf(draft, null));
	return presets.find((preset) => key(preset.profile) === mine)?.id ?? null;
}

/** Presets name months and leave dates unset; the draft always sets both. */
function normalise(profile: SeedProfile): SeedProfile {
	const dates = (config: { date_from?: string | null; date_to?: string | null }) => ({
		date_from: config.date_from ?? null,
		date_to: config.date_to ?? null
	});
	return {
		...profile,
		workout_config: { ...profile.workout_config, ...dates(profile.workout_config) },
		sleep_config: { ...profile.sleep_config, ...dates(profile.sleep_config) },
		time_series_config: { ...profile.time_series_config, ...dates(profile.time_series_config) }
	};
}

const between = (value: number, [low, high]: readonly [number, number]) =>
	isWholeIn(value, low, high);

const ordered = ([low, high]: Range) =>
	Number.isFinite(low) && Number.isFinite(high) && low <= high;

/** Everything that stops the request going out, in the reader's words. */
export function problems(draft: Draft): string[] {
	const found: string[] = [];
	const need = (ok: boolean, message: string) => ok || found.push(message);

	need(between(draft.users, LIMITS.users), 'Users must be 1 to 10.');
	need(
		draft.seed === null || (Number.isSafeInteger(draft.seed) && draft.seed >= 0),
		'The seed must be a whole number, or empty for a random one.'
	);
	need(draft.providers.length <= MAX_CONNECTIONS, `Pick at most ${MAX_CONNECTIONS} providers.`);
	if (draft.providers.length === 0) {
		need(between(draft.connections, LIMITS.connections), 'Connections must be 1 to 5.');
	}

	if ('months' in draft.window) {
		need(between(draft.window.months, LIMITS.months), 'The window must be 1 to 24 months.');
	} else {
		need(
			Boolean(draft.window.from && draft.window.to) && draft.window.from <= draft.window.to,
			'The window needs a start that is not after its end.'
		);
	}

	need(
		draft.workouts.on || draft.sleep.on || draft.series.on,
		'Turn on at least one kind of data.'
	);

	if (draft.workouts.on) {
		const w = draft.workouts;
		need(between(w.count, LIMITS.workouts), 'Workouts must be 0 to 500.');
		need(
			ordered(w.duration) && w.duration.every((minutes) => between(minutes, LIMITS.workoutMinutes)),
			'Workout length must run low to high, within 5 to 600 minutes.'
		);
		need(ordered(w.hrMin) && ordered(w.hrMax), 'Heart rate ranges must run low to high.');
		need(ordered(w.steps) && w.steps[0] >= 0, 'The step range must run low to high.');
		need(w.types === null || w.types.length > 0, 'Pick at least one workout type, or all of them.');
	}

	if (draft.sleep.on) {
		const s = draft.sleep;
		need(between(s.count, LIMITS.nights), 'Nights must be 0 to 365.');
		need(
			ordered(s.duration) && s.duration.every((minutes) => between(minutes, LIMITS.sleepMinutes)),
			'Sleep length must run low to high, within 1 to 12 hours.'
		);
		need(between(s.napChance, LIMITS.percent), 'Nap chance must be 0 to 100%.');
		if (s.stageProfile === null) {
			const stages = [s.deep, s.rem, s.awake];
			need(
				stages.every(
					(range) => ordered(range) && range.every((pct) => between(pct, LIMITS.percent))
				),
				'Stage shares must run low to high, within 0 to 100%.'
			);
			need(
				stages.reduce((sum, [low]) => sum + low, 0) <= 100,
				'The lowest stage shares add up to more than a whole night.'
			);
		}
	}

	if (draft.series.on) {
		need(
			draft.series.types.length > 0 || draft.series.bloodPressure,
			'Pick at least one series type, or turn time series off.'
		);
	}

	return found;
}

/** The named profile's ranges, or the draft's own when it has none. */
export function stagesOf(sleep: Draft['sleep'], profiles: SleepProfile[]) {
	const named = profiles.find((profile) => profile.id === sleep.stageProfile);
	return named
		? {
				deep: named.distribution.deep_pct_range,
				rem: named.distribution.rem_pct_range,
				awake: named.distribution.awake_pct_range
			}
		: { deep: sleep.deep, rem: sleep.rem, awake: sleep.awake };
}

export const CREDENTIALS = { email: 'dev@example.com', password: 'correct-horse' };

export const DEVELOPER = {
	id: '00000000-0000-4000-8000-000000000001',
	email: CREDENTIALS.email,
	first_name: 'Test',
	last_name: 'Developer',
	created_at: '2026-01-01T00:00:00Z'
};

export const PROVIDERS = ['garmin', 'oura', 'whoop', 'suunto'];

export const PROVIDER_SETTINGS = PROVIDERS.map((provider) => ({
	provider,
	name: provider[0].toUpperCase() + provider.slice(1),
	has_cloud_api: true,
	is_enabled: true,
	icon_url: `/static/provider-icons/${provider}.svg`
}));

/** 47 users: enough for three pages at 20, with a memorable one to search for. */
/** Mirrors UserRead; declared here so e2e files need no $lib alias. */
export type MockUser = {
	id: string;
	created_at: string;
	first_name: string | null;
	last_name: string | null;
	email: string | null;
	external_user_id: string | null;
	last_synced_at: string | null;
	last_synced_provider: string | null;
	has_active_connection: boolean;
	connections: { provider: string; status: 'active'; last_synced_at: string }[];
};

/** A fresh set per test: the mock mutates its copy. */
export const makeUsers = (): MockUser[] =>
	Array.from({ length: 47 }, (_, index) => {
		const n = index + 1;
		return {
			id: `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`,
			created_at: new Date(Date.UTC(2026, 0, 1 + n)).toISOString(),
			first_name: n === 7 ? 'Zofia' : `User${n}`,
			last_name: n === 7 ? 'Kowalska' : 'Test',
			email: n === 7 ? 'zofia@example.com' : `user${n}@example.com`,
			external_user_id: `ext-${String(n).padStart(4, '0')}`,
			last_synced_at: n % 3 === 0 ? null : new Date(Date.UTC(2026, 8, 1 + (n % 4))).toISOString(),
			last_synced_provider: n % 3 === 0 ? null : PROVIDERS[n % PROVIDERS.length],
			has_active_connection: n % 3 !== 0,
			connections:
				n % 3 === 0
					? []
					: [
							{
								provider: PROVIDERS[n % PROVIDERS.length],
								status: 'active' as const,
								last_synced_at: new Date(Date.UTC(2026, 8, 1 + (n % 4))).toISOString()
							}
						]
		};
	});

export type MockConnection = {
	id: string;
	user_id: string;
	provider: string;
	provider_user_id: string | null;
	provider_username: string | null;
	scope: string | null;
	status: 'active' | 'revoked' | 'expired';
	last_synced_at: string | null;
	created_at: string;
	updated_at: string;
	icon_url: string | null;
	max_historical_days: number | null;
	rest_pull: boolean;
	webhook_stream: boolean;
	webhook_ping: boolean;
	webhook_callback: boolean;
	live_sync_mode: string | null;
	linked_user_ids: string[];
};

/**
 * Mirrors UserConnectionWithCapabilities, with each provider's real
 * capabilities — the backend rejects webhook_stream together with webhook_ping,
 * so a fixture must not set both. Three cards: one webhook-only provider (no
 * Sync now), one pull provider (both buttons), one expired (no buttons).
 */
export const makeConnections = (userId: string): MockConnection[] => [
	{
		id: `${userId}-garmin`,
		user_id: userId,
		provider: 'garmin',
		provider_user_id: 'garmin-42',
		provider_username: 'zofia.k',
		scope: 'activity sleep',
		status: 'active',
		last_synced_at: '2026-09-04T06:30:00Z',
		created_at: '2026-02-01T10:00:00Z',
		updated_at: '2026-09-04T06:30:00Z',
		icon_url: '/static/provider-icons/garmin.svg',
		max_historical_days: 30,
		rest_pull: false,
		webhook_stream: true,
		webhook_ping: false,
		webhook_callback: true,
		live_sync_mode: 'webhook',
		linked_user_ids: []
	},
	{
		id: `${userId}-oura`,
		user_id: userId,
		provider: 'oura',
		provider_user_id: 'oura-7',
		provider_username: null,
		scope: 'personal daily heartrate workout',
		status: 'active',
		last_synced_at: '2026-09-03T22:05:00Z',
		created_at: '2026-03-11T09:00:00Z',
		updated_at: '2026-09-03T22:05:00Z',
		icon_url: '/static/provider-icons/oura.svg',
		max_historical_days: null,
		rest_pull: true,
		webhook_stream: false,
		webhook_ping: true,
		webhook_callback: false,
		live_sync_mode: 'pull',
		linked_user_ids: ['00000000-0000-4000-8000-000000000009']
	},
	{
		id: `${userId}-suunto`,
		user_id: userId,
		provider: 'suunto',
		provider_user_id: 'suunto-3',
		provider_username: null,
		// Garmin and Suunto configure an empty scope, so there is no badge at all.
		scope: null,
		status: 'expired',
		last_synced_at: '2026-07-19T22:05:00Z',
		created_at: '2026-04-02T09:00:00Z',
		updated_at: '2026-07-19T22:05:00Z',
		icon_url: '/static/provider-icons/suunto.svg',
		max_historical_days: null,
		rest_pull: true,
		webhook_stream: true,
		webhook_ping: false,
		webhook_callback: false,
		live_sync_mode: 'webhook',
		linked_user_ids: []
	}
];

/** Postgres-backed: historical runs only, and not limited to 24h. */
export const makeSyncHistory = (userId: string) => [
	{
		run_key: 'run_hist_1',
		user_id: userId,
		provider: 'garmin',
		source: 'backfill',
		scope: 'historical' as const,
		status: 'success' as const,
		trace_id: null,
		window_start: '2026-08-05T00:00:00Z',
		window_end: '2026-09-04T00:00:00Z',
		started_at: '2026-09-04T06:00:00Z',
		ended_at: '2026-09-04T06:04:30Z',
		items_inserted: 8421,
		items_updated: 12,
		error: null
	},
	{
		run_key: 'run_hist_2',
		user_id: userId,
		provider: 'oura',
		source: 'pull',
		scope: 'historical' as const,
		status: 'failed' as const,
		trace_id: null,
		window_start: '2025-07-19T00:00:00Z',
		window_end: '2026-07-19T00:00:00Z',
		started_at: '2026-07-19T22:00:00Z',
		ended_at: '2026-07-19T22:05:00Z',
		items_inserted: 0,
		items_updated: 0,
		error: 'Token expired while fetching daily_sleep'
	}
];

/** Redis-backed: last 24h, every scope. */
export const makeRecentRuns = (userId: string) => [
	{
		run_id: 'run_live_1',
		user_id: userId,
		provider: 'garmin',
		source: 'webhook',
		stage: 'processing',
		status: 'in_progress',
		message: 'Writing heart rate samples',
		progress: 0.6,
		items_processed: 120,
		items_total: 200,
		error: null,
		started_at: '2026-09-05T08:00:00Z',
		ended_at: null,
		last_update: '2026-09-05T08:01:00Z'
	},
	{
		run_id: 'run_live_2',
		user_id: userId,
		provider: 'oura',
		source: 'pull',
		stage: 'completed',
		status: 'success',
		message: null,
		progress: 1,
		items_processed: 48,
		items_total: 48,
		error: null,
		started_at: '2026-09-05T05:00:00Z',
		ended_at: '2026-09-05T05:00:20Z',
		last_update: '2026-09-05T05:00:20Z',
		// Reports its counts, so the row shows them instead of the message. The
		// Garmin run above reports none, which is what the API does today.
		items_inserted: 19058,
		items_updated: 10223
	}
];

const isoDay = (offset: number, weekAligned = false) => {
	const date = new Date();
	date.setUTCHours(0, 0, 0, 0);
	date.setUTCDate(date.getUTCDate() - offset);
	// date_trunc('week') is Monday-based; unaligned dates would match no cell.
	if (weekAligned) date.setUTCDate(date.getUTCDate() - ((date.getUTCDay() + 6) % 7));
	return date.toISOString().slice(0, 10);
};

export const makeDataSummary = () => ({
	total_data_points: 51420,
	total_workouts: 63,
	total_sleep_events: 88,
	series_type_counts: {
		heart_rate: 38110,
		steps: 6400,
		oxygen_saturation: 3120,
		respiratory_rate: 1900,
		body_temperature: 980,
		stress_level: 640,
		vo2_max: 210,
		hydration: 40,
		uv_exposure: 20
	},
	workout_type_counts: { running: 31, cycling: 18, swimming: 9, strength_training: 5 },
	by_provider: [
		{
			provider: 'garmin',
			data_points: 44000,
			series_counts: { heart_rate: 38110, steps: 5890 },
			workout_count: 51,
			sleep_count: 60
		},
		{
			provider: 'oura',
			data_points: 7420,
			series_counts: { oxygen_saturation: 3120, respiratory_rate: 1900 },
			workout_count: 12,
			sleep_count: 28
		}
	],
	has_womens_health_data: true
});

/** Which provider delivers what, so the provider filter has something to cut. */
const SERIES_OWNER: Record<string, string> = {
	heart_rate: 'garmin',
	steps: 'garmin',
	vo2_max: 'garmin',
	oxygen_saturation: 'oura',
	sleep_duration: 'oura'
};

const WORKOUT_OWNER: Record<string, string> = {
	running: 'garmin',
	cycling: 'garmin',
	strength_training: 'garmin',
	swimming: 'oura',
	open_water_swimming: 'suunto'
};

/**
 * Relative to today, so the cells land inside the grid the page computes, and
 * covering the whole default window rather than a corner of it. Garmin has a
 * deliberate week-long gap: the thing the heatmap exists to show.
 */
export const makeDataTimeline = (bucket: string, groupBy: string, provider = '') => {
	const weekly = bucket === 'week';
	const stride = weekly ? 7 : 1;
	const count = weekly ? 52 : 90;

	// A wave, so intensity varies instead of every cell landing on one shade.
	const wave = (index: number) => 0.35 + 0.65 * Math.abs(Math.sin(index / 6));
	const owned = (owner: Record<string, string>) => (key: string) =>
		!provider || owner[key] === provider;

	const series = (
		keys: string[],
		metric: string,
		fill: (key: string, index: number, rank: number) => number | null
	) =>
		keys.map((key, rank) => {
			const buckets: [string, number][] = [];
			for (let index = 0; index < count; index += 1) {
				const value = fill(key, index, rank);
				if (value !== null) buckets.push([isoDay(index * stride, weekly), value]);
			}
			return { key, metric, buckets: buckets.reverse() };
		});

	if (groupBy === 'series_type') {
		// Sleep stops arriving partway through: the pattern a per-type heatmap is
		// for, and invisible in a per-provider one.
		const types = Object.keys(SERIES_OWNER).filter(owned(SERIES_OWNER));
		return {
			bucket,
			group_by: groupBy,
			series: series(types, 'data_points', (key, index, rank) => {
				if (key === 'sleep_duration' && index < 20) return null;
				if (key === 'vo2_max' && index % 7 !== 0) return null;
				return Math.round((2400 / (rank + 1)) * wave(index));
			})
		};
	}

	if (groupBy === 'workout_type') {
		const types = Object.keys(WORKOUT_OWNER).filter(owned(WORKOUT_OWNER));
		return {
			bucket,
			group_by: groupBy,
			// Workouts are counted, not sampled, so these are single digits.
			series: series(types, 'workouts', (key, index, rank) => {
				if ((index + rank) % (rank + 2) !== 0) return null;
				return 1 + (index % (3 - Math.min(rank, 2)));
			})
		};
	}

	const providers = ['garmin', 'oura'].filter((key) => !provider || key === provider);
	return {
		bucket,
		group_by: groupBy,
		series: series(providers, 'data_points', (key, index) => {
			if (key === 'garmin')
				return index >= 10 && index <= 16 ? null : Math.round(2100 * wave(index));
			return index % 3 === 0 ? Math.round(420 * wave(index)) : null;
		})
	};
};

/** Model and kind, so the card's device icon has something to vary on. */
const DEVICES: Record<string, { model: string; type: string }> = {
	garmin: { model: 'Forerunner 265', type: 'watch' },
	oura: { model: 'Oura Ring Gen3', type: 'ring' },
	suunto: { model: 'Suunto 9 Peak', type: 'watch' }
};

/**
 * Shaped after what each provider actually delivers, nulls included: Oura
 * reports no heart rate for workouts and strength training has no distance, so
 * the cards have real gaps to render rather than a full row every time.
 */
const WORKOUT_SHAPES = [
	{ type: 'running', minutes: 48, distance: 8200, calories: 512, avgHr: 148, maxHr: 176 },
	{ type: 'cycling', minutes: 92, distance: 41200, calories: 980, avgHr: 139, maxHr: 171 },
	{ type: 'strength_training', minutes: 35, distance: 0, calories: 240, avgHr: 119, maxHr: 158 },
	{ type: 'swimming', minutes: 40, distance: 1500, calories: 310, avgHr: 0, maxHr: 0 },
	// Long enough to finish on the following day, like the real open-water swims:
	// the case where the range needs to say which day it ended on.
	{
		type: 'open_water_swimming',
		minutes: 229,
		distance: 9400,
		calories: 1480,
		avgHr: 131,
		maxHr: 158,
		// 20:30Z is 22:30 in the fixture's +02:00, so it finishes after local midnight.
		startsAt: '20:30'
	}
];

const HR_ZONES = {
	zones: [
		{ zone: 0, seconds: 240, max_bpm: 114 },
		{ zone: 1, seconds: 620, max_bpm: 133 },
		{ zone: 2, seconds: 980, max_bpm: 152 },
		{ zone: 3, seconds: 810, max_bpm: 171 },
		{ zone: 4, seconds: 230, max_bpm: 190 }
	],
	max_hr: 190,
	threshold_hr: 165
};

const POWER_ZONES = {
	zones: [
		{ zone: 0, seconds: 300, max_watts: 138 },
		{ zone: 1, seconds: 900, max_watts: 184 },
		{ zone: 2, seconds: 1800, max_watts: 219 },
		{ zone: 3, seconds: 1400, max_watts: 253 },
		{ zone: 4, seconds: 1120, max_watts: 345 }
	],
	ftp_watts: 230
};

const nullable = (value: number) => (value > 0 ? value : null);

const buildWorkouts = () =>
	Array.from({ length: 23 }, (_, index) => {
		const shape = WORKOUT_SHAPES[index % WORKOUT_SHAPES.length];
		const provider = WORKOUT_OWNER[shape.type];
		const seconds = shape.minutes * 60;
		const start = new Date(`${isoDay(index * 3)}T${shape.startsAt ?? '07:12'}:00.000Z`);

		return {
			id: `w0000000-0000-4000-8000-${String(index).padStart(12, '0')}`,
			type: shape.type,
			name: index % 4 === 0 ? 'Morning session' : null,
			start_time: start.toISOString(),
			end_time: new Date(start.getTime() + seconds * 1000).toISOString(),
			zone_offset: '+02:00',
			duration_seconds: seconds,
			source: {
				provider,
				source: provider,
				device: DEVICES[provider].model,
				device_type: DEVICES[provider].type,
				device_name: DEVICES[provider].model
			},
			entry_source: 'automatic',
			intensity: 'moderate',
			calories_kcal: shape.calories,
			distance_meters: nullable(shape.distance),
			avg_heart_rate_bpm: nullable(shape.avgHr),
			max_heart_rate_bpm: nullable(shape.maxHr),
			heart_rate_min: nullable(shape.avgHr && shape.avgHr - 42),
			avg_pace_sec_per_km:
				shape.distance > 0 ? Math.round((seconds / shape.distance) * 1000) : null,
			elevation_gain_meters: shape.distance > 0 ? 120 : null,
			steps_count: shape.type === 'running' ? 9400 : null,
			average_speed: null,
			max_speed: null,
			average_cadence: shape.type === 'running' ? 168 : null,
			average_watts: shape.type === 'cycling' ? 212 : null,
			max_watts: shape.type === 'cycling' ? 640 : null,
			moving_time_seconds: seconds,
			elev_high: null,
			elev_low: null,
			// Only Whoop and Garmin (from a FIT file) report these, and power only
			// where there is a crank to measure it.
			hr_zones: provider === 'garmin' ? HR_ZONES : null,
			power_zones: provider === 'garmin' && shape.type === 'cycling' ? POWER_ZONES : null,
			segments: null
		};
	});

let WORKOUTS = buildWorkouts();

/** Restores the list `deleteWorkout` mutates, so /__reset gives every test 23. */
export const resetWorkouts = () => {
	WORKOUTS = buildWorkouts();
};

/**
 * Base64 of the record it points at, and `prev_`-prefixed going backwards —
 * the same opaque shape `app/utils/pagination.py` emits. A counter would have
 * hidden any mangling of the real thing on its way through the URL.
 */
const encodeCursor = (id: string, direction: 'next' | 'prev') =>
	(direction === 'prev' ? 'prev_' : '') + btoa(id);

const decodeCursor = (cursor: string) => ({
	id: atob(cursor.replace(/^prev_/, '')),
	backwards: cursor.startsWith('prev_')
});

/** Keyset paging, like the API: the cursor is a position, not a page number. */
export const makeWorkouts = (query: URLSearchParams) => {
	const provider = query.get('provider') ?? '';
	const type = query.get('type') ?? '';
	const limit = Number(query.get('limit') ?? 50);
	const start = new Date(query.get('start_date') ?? 0).getTime();
	const end = new Date(query.get('end_date') ?? 0).getTime();

	const matching = WORKOUTS.filter((workout) => {
		const at = new Date(workout.start_time).getTime();
		if (at < start || at >= end) return false;
		if (provider && workout.source.provider !== provider) return false;
		return !type || workout.type === type;
	});

	const cursor = query.get('cursor');
	const { id, backwards } = cursor ? decodeCursor(cursor) : { id: '', backwards: false };
	const found = cursor ? matching.findIndex((workout) => workout.id === id) : -1;

	// Cursor handling mirrors event_record_service.get_workouts line for line,
	// quirk included: going backwards, `has_more` means "records exist before this
	// page" and the same flag gates next_cursor — so page one reached by a prev_
	// cursor comes back with neither cursor and strands the reader.
	const offset = backwards ? Math.max(found - limit, 0) : found + 1;
	const hasMore = backwards ? found > limit : offset + limit < matching.length;
	const data = matching.slice(offset, offset + limit);

	const previous = cursor && data.length && (!backwards || hasMore);

	return {
		data,
		pagination: {
			next_cursor: hasMore && data.length ? encodeCursor(data[data.length - 1].id, 'next') : null,
			previous_cursor: previous ? encodeCursor(data[0].id, 'prev') : null,
			has_more: hasMore,
			total_count: matching.length
		}
	};
};

/** Mutates the shared list, like the API does: the next page load must agree. */
export const deleteWorkout = (id: string) => {
	const index = WORKOUTS.findIndex((workout) => workout.id === id);
	if (index === -1) return false;
	WORKOUTS.splice(index, 1);
	return true;
};

const STEP_MS: Record<string, number> = {
	raw: 60_000,
	'1min': 60_000,
	'5min': 300_000,
	'15min': 900_000,
	'1hour': 3_600_000
};

/**
 * A plausible curve rather than noise: a warm-up, two efforts and a cool-down,
 * so the chart has a shape to read and the zone bands have something to band.
 */
const heartRateAt = (fraction: number) =>
	Math.round(112 + 46 * Math.sin(fraction * Math.PI) + 14 * Math.sin(fraction * Math.PI * 6));

export const makeTimeseries = (query: URLSearchParams) => {
	const types = query.getAll('types');
	const start = new Date(query.get('start_time') ?? 0).getTime();
	const end = new Date(query.get('end_time') ?? 0).getTime();
	const step = STEP_MS[query.get('resolution') ?? 'raw'] ?? 60_000;

	const workout = WORKOUTS.find((entry) => new Date(entry.start_time).getTime() === start);
	const data: Record<string, unknown>[] = [];

	for (let at = start; at <= end && data.length < 2000; at += step) {
		const fraction = (at - start) / Math.max(end - start, 1);

		// A whole day asks for movement rather than a session's sensors, and the
		// daily totals ride the same endpoint — the chart has to drop those.
		if (types.includes('steps')) {
			data.push({
				timestamp: new Date(at).toISOString(),
				zone_offset: '+02:00',
				source: { provider: 'garmin', device: 'Forerunner 265', device_name: 'Forerunner 265' },
				is_daily_total: false,
				type: 'steps',
				value: Math.round(40 + 90 * Math.abs(Math.sin(fraction * Math.PI * 4))),
				unit: 'count'
			});
		}

		const sample = {
			timestamp: new Date(at).toISOString(),
			zone_offset: '+02:00',
			source: {
				provider: workout?.source.provider ?? 'garmin',
				device: workout?.source.device ?? null,
				device_name: workout?.source.device_name ?? null
			},
			is_daily_total: false
		};

		// Activity asks over a whole day, where no workout starts the window.
		if (types.includes('heart_rate') && (workout?.avg_heart_rate_bpm || types.includes('steps'))) {
			data.push({ ...sample, type: 'heart_rate', value: heartRateAt(fraction), unit: 'bpm' });
		}
		// Only the bike reports power, so only its card gets a second line.
		if (types.includes('power') && workout?.average_watts) {
			data.push({
				...sample,
				type: 'power',
				value: Math.round(150 + 120 * Math.abs(Math.sin(fraction * Math.PI * 3))),
				unit: 'watts'
			});
		}
	}

	// A second device in the same window, so the chart has to keep the two curves
	// apart rather than sawing between them. Only the run, so other cards stay clean.
	if (types.includes('heart_rate') && workout?.type === 'running') {
		for (let at = start; at <= end; at += step * 2) {
			const fraction = (at - start) / Math.max(end - start, 1);
			data.push({
				timestamp: new Date(at).toISOString(),
				zone_offset: '+02:00',
				source: { provider: 'apple', device: 'Watch7,1', device_name: 'Apple Watch' },
				is_daily_total: false,
				type: 'heart_rate',
				value: heartRateAt(fraction) - 9,
				unit: 'bpm'
			});
		}
	}

	return { data, pagination: { has_more: false, total_count: data.length } };
};

/**
 * Oura reports stage intervals, Suunto only the per-stage minutes — the split
 * the cards have to render differently. Naps every fifth night.
 */
const SLEEP_SHAPES = [
	{ provider: 'oura', asleep: 25_500, inBed: 27_600, efficiency: 92, intervals: true },
	{ provider: 'suunto', asleep: 21_000, inBed: 24_300, efficiency: 86, intervals: false }
];

const STAGE_CYCLE: StageName[] = ['awake', 'light', 'deep', 'light', 'rem'];
type StageName = 'awake' | 'light' | 'deep' | 'rem';

const stageMinutes = (asleep: number) => ({
	awake_minutes: Math.round((asleep * 0.06) / 60),
	light_minutes: Math.round((asleep * 0.52) / 60),
	deep_minutes: Math.round((asleep * 0.21) / 60),
	rem_minutes: Math.round((asleep * 0.21) / 60)
});

/** Cycles of the real shape: light, deep, light, REM, with brief wakings. */
function stageIntervals(start: number, seconds: number) {
	const out: { stage: StageName; start_time: string; end_time: string }[] = [];
	let at = start;
	const step = Math.floor(seconds / 20);

	for (let index = 0; index < 20; index += 1) {
		const stage = STAGE_CYCLE[index % STAGE_CYCLE.length];
		const length = stage === 'awake' ? Math.round(step / 4) : step;
		out.push({
			stage,
			start_time: new Date(at).toISOString(),
			end_time: new Date(at + length * 1000).toISOString()
		});
		at += length * 1000;
	}

	return out;
}

const buildSleep = () =>
	Array.from({ length: 17 }, (_, index) => {
		const shape = SLEEP_SHAPES[index % SLEEP_SHAPES.length];
		const isNap = index % 5 === 4;
		const inBed = isNap ? 4200 : shape.inBed;
		const asleep = isNap ? 3600 : shape.asleep;
		// Nights start the evening before; naps sit in the afternoon.
		const start = new Date(`${isoDay(index * 2 + 1)}T${isNap ? '13:20' : '22:40'}:00.000Z`);

		return {
			id: `s0000000-0000-4000-8000-${String(index).padStart(12, '0')}`,
			start_time: start.toISOString(),
			end_time: new Date(start.getTime() + inBed * 1000).toISOString(),
			zone_offset: '+02:00',
			source: {
				provider: shape.provider,
				source: shape.provider,
				device: DEVICES[shape.provider].model,
				device_type: DEVICES[shape.provider].type,
				device_name: DEVICES[shape.provider].model
			},
			duration_seconds: inBed,
			sleep_duration_seconds: asleep,
			time_in_bed_seconds: inBed,
			efficiency_percent: shape.efficiency,
			stages: stageMinutes(asleep),
			sleep_stage_intervals: shape.intervals ? stageIntervals(start.getTime(), asleep) : null,
			is_nap: isNap
		};
	});

let SLEEP = buildSleep();

/** Restores the list `deleteSleep` mutates, so /__reset gives every test 17. */
export const resetSleep = () => {
	SLEEP = buildSleep();
};

export const deleteSleep = (id: string) => {
	const index = SLEEP.findIndex((session) => session.id === id);
	if (index === -1) return false;
	SLEEP.splice(index, 1);
	return true;
};

/** Keyset paging and the same cursor shape as the workouts list. */
export const makeSleep = (query: URLSearchParams) => {
	const provider = query.get('provider') ?? '';
	const limit = Number(query.get('limit') ?? 50);
	const start = new Date(query.get('start_date') ?? 0).getTime();
	const end = new Date(query.get('end_date') ?? 0).getTime();
	const withStages = query.getAll('include').includes('stages');

	let matching = SLEEP.filter((session) => {
		const at = new Date(session.start_time).getTime();
		if (at < start || at >= end) return false;
		return !provider || session.source.provider === provider;
	});

	// Oura outranks Suunto in the default priority order, so the winning source
	// per night is the Oura one wherever both reported.
	if (query.get('filter_by_priority') === 'true') {
		matching = matching.filter((session) => session.source.provider === 'oura');
	}

	const cursor = query.get('cursor');
	const { id, backwards } = cursor ? decodeCursor(cursor) : { id: '', backwards: false };
	const found = cursor ? matching.findIndex((session) => session.id === id) : -1;

	const offset = backwards ? Math.max(found - limit, 0) : found + 1;
	const hasMore = backwards ? found > limit : offset + limit < matching.length;
	const data = matching.slice(offset, offset + limit).map((session) => ({
		...session,
		sleep_stage_intervals: withStages ? session.sleep_stage_intervals : null
	}));

	const previous = cursor && data.length && (!backwards || hasMore);

	return {
		data,
		pagination: {
			next_cursor: hasMore && data.length ? encodeCursor(data[data.length - 1].id, 'next') : null,
			previous_cursor: previous ? encodeCursor(data[0].id, 'prev') : null,
			has_more: hasMore,
			total_count: matching.length
		}
	};
};

/** What `/events/workouts/types` answers: the types this user actually has. */
export const workoutTypes = () => [...new Set(WORKOUTS.map((workout) => workout.type))].sort();

/**
 * One row a day, newest first, as the endpoint answers after keeping the
 * highest-priority source per date. A few gaps, because a day nobody wore the
 * watch is the thing an admin is usually looking for.
 */
const buildActivity = () =>
	Array.from({ length: 24 }, (_, index) => index)
		.filter((index) => index % 7 !== 3)
		.map((index) => {
			const provider = index % 3 === 0 ? 'oura' : 'garmin';
			const steps = 5200 + ((index * 1373) % 7400);

			return {
				date: isoDay(index),
				source: {
					provider,
					source: provider,
					device: DEVICES[provider].model,
					device_type: DEVICES[provider].type,
					device_name: DEVICES[provider].model
				},
				steps,
				distance_meters: Math.round(steps * 0.72),
				floors_climbed: index % 4 === 0 ? 8 + (index % 5) : null,
				elevation_meters: index % 4 === 0 ? 24 + index : null,
				active_calories_kcal: Math.round(steps * 0.042),
				total_calories_kcal: 1650 + Math.round(steps * 0.042),
				active_minutes: 40 + (index % 50),
				sedentary_minutes: 600 - (index % 90),
				intensity_minutes:
					provider === 'garmin'
						? { light: 30 + (index % 20), moderate: 12 + (index % 9), vigorous: index % 7 }
						: null,
				heart_rate: { avg_bpm: 62 + (index % 9), max_bpm: 141 + (index % 20), min_bpm: 48 }
			};
		});

let ACTIVITY = buildActivity();

export const resetActivity = () => {
	ACTIVITY = buildActivity();
};

/** Keyset paging and the same cursor shape as the other lists. */
export const makeActivity = (query: URLSearchParams) => {
	const limit = Number(query.get('limit') ?? 50);
	const start = new Date(query.get('start_date') ?? 0).getTime();
	const end = new Date(query.get('end_date') ?? 0).getTime();

	const matching = ACTIVITY.filter((day) => {
		const at = new Date(`${day.date}T12:00:00Z`).getTime();
		return at >= start && at < end;
	});

	const cursor = query.get('cursor');
	const { id, backwards } = cursor ? decodeCursor(cursor) : { id: '', backwards: false };
	const found = cursor ? matching.findIndex((day) => day.date === id) : -1;

	const offset = backwards ? Math.max(found - limit, 0) : found + 1;
	const hasMore = backwards ? found > limit : offset + limit < matching.length;
	const data = matching.slice(offset, offset + limit);
	const previous = cursor && data.length && (!backwards || hasMore);

	return {
		data,
		pagination: {
			next_cursor: hasMore && data.length ? encodeCursor(data[data.length - 1].date, 'next') : null,
			previous_cursor: previous ? encodeCursor(data[0].date, 'prev') : null,
			has_more: hasMore,
			// Faithful to the endpoint: it builds Pagination without a count, so the
			// bar has no last page to name and must not invent one.
			total_count: null
		}
	};
};

/** Mirrors `BodySummary`, including the nulls: this user was never weighed for
 *  body fat, and nothing was measured recently enough to be `latest`. */
export const makeBody = () => ({
	source: {
		provider: 'garmin',
		source: 'garmin',
		device: DEVICES.garmin.model,
		device_type: DEVICES.garmin.type,
		device_name: DEVICES.garmin.model
	},
	slow_changing: {
		weight_kg: 74.3,
		height_cm: 181,
		body_fat_percent: null,
		muscle_mass_kg: 59.4,
		bmi: 22.7,
		age: 34
	},
	averaged: {
		period_days: 7,
		resting_heart_rate_bpm: 54,
		avg_hrv_sdnn_ms: null,
		avg_hrv_rmssd_ms: 41.8,
		period_start: `${isoDay(7)}T00:00:00Z`,
		period_end: `${isoDay(0)}T00:00:00Z`
	},
	latest: {
		body_temperature_celsius: null,
		body_temperature_measured_at: null,
		skin_temperature_celsius: null,
		skin_temperature_measured_at: null,
		blood_pressure: null,
		blood_pressure_measured_at: null
	}
});

const VITAL_SHAPES: Record<string, { unit: string; base: number; swing: number; perDay: number }> =
	{
		resting_heart_rate: { unit: 'bpm', base: 54, swing: 5, perDay: 1 },
		// Dozens a day, which is why the trend has to average before it draws.
		heart_rate_variability_rmssd: { unit: 'ms', base: 42, swing: 9, perDay: 24 },
		oxygen_saturation: { unit: 'percent', base: 96, swing: 2, perDay: 1 },
		// One reading only, so it has no line to draw and must not claim one.
		weight: { unit: 'kg', base: 74.3, swing: 0, perDay: 0 }
	};

/** Daily-ish vitals across the window, so the trends have something to average. */
export const makeVitals = (query: URLSearchParams) => {
	const types = query.getAll('types');
	const start = new Date(query.get('start_time') ?? 0).getTime();
	const end = new Date(query.get('end_time') ?? 0).getTime();
	const days = Math.max(Math.round((end - start) / 86_400_000), 1);

	const data: Record<string, unknown>[] = [];

	for (const [type, shape] of Object.entries(VITAL_SHAPES)) {
		if (!types.includes(type)) continue;

		const readings = shape.perDay === 0 ? 1 : days * shape.perDay;
		for (let index = 0; index < readings && data.length < 4000; index += 1) {
			data.push({
				timestamp: new Date(start + (index / readings) * (end - start)).toISOString(),
				zone_offset: '+02:00',
				source: { provider: 'garmin', device: 'Forerunner 265', device_name: 'Forerunner 265' },
				is_daily_total: false,
				type,
				value:
					Math.round((shape.base + shape.swing * Math.sin(index / (shape.perDay * 3 || 3))) * 10) /
					10,
				unit: shape.unit
			});
		}
	}

	return { data, pagination: { has_more: false, total_count: data.length } };
};

/**
 * Health scores as the real table holds them: the same night scored by two
 * providers, a category whose readable score hides in a component, and one
 * provider that scores through the day instead of once.
 */
const SCORE_SHAPES = [
	{ category: 'sleep', provider: 'oura', perDay: 1, base: 82, swing: 10 },
	{ category: 'sleep', provider: 'internal', perDay: 1, base: 76, swing: 12 },
	{ category: 'readiness', provider: 'oura', perDay: 1, base: 74, swing: 16 },
	{ category: 'activity', provider: 'oura', perDay: 1, base: 88, swing: 8 },
	// Suunto's stress-recovery stream: many a day, each with a rating.
	{ category: 'recovery', provider: 'suunto', perDay: 8, base: 48, swing: 26 },
	// The odd one: `value` is the HRV coefficient of variation, and the 0-100
	// score sits in `components.resilience_score`.
	{ category: 'resilience', provider: 'internal', perDay: 1, base: 0, swing: 0 }
] as const;

const STRESS_STATES = ['Relaxing', 'Active', 'Passive', 'Stressful'];

const SCORE_COMPONENTS: Record<string, string[]> = {
	'sleep:oura': ['total_sleep', 'efficiency', 'restfulness', 'timing'],
	'sleep:internal': ['duration', 'stages', 'consistency', 'interruptions'],
	'readiness:oura': ['hrv_balance', 'resting_heart_rate', 'previous_night'],
	'activity:oura': ['stay_active', 'move_every_hour', 'training_volume']
};

/** Smooth, the way seven days of HRV variability actually move. */
const resilienceScore = (day: number) => Math.round(74 + 16 * Math.sin(day / 4));

const buildScores = () => {
	const rows: Record<string, unknown>[] = [];

	// A hundred and ten days: longer than the ninety-day range preset, so a test
	// can tell "All time" from it by the number of days the bar counts.
	for (let day = 0; day < 110; day += 1) {
		for (const shape of SCORE_SHAPES) {
			for (let index = 0; index < shape.perDay; index += 1) {
				const step = day * 7 + index * 3;
				const hour = shape.perDay === 1 ? 2 : 1 + index * 2;
				// A daily swing plus a within-day one, so a stream's mean moves from day
				// to day instead of averaging out to the same number every time.
				const value = Math.round(
					shape.base +
						shape.swing * Math.sin(day / 3) +
						(shape.perDay > 1 ? 24 * Math.sin(index) : 0)
				);

				const key = `${shape.category}:${shape.provider}`;
				const components: Record<string, unknown> = Object.fromEntries(
					(SCORE_COMPONENTS[key] ?? []).map((name, position) => [
						name,
						{ value: Math.min(100, value + position * 4), qualifier: null }
					])
				);

				if (shape.category === 'recovery') {
					components.stress_state = {
						value: step % 4,
						qualifier: STRESS_STATES[step % STRESS_STATES.length]
					};
				}

				rows.push({
					id: `score-${day}-${shape.category}-${shape.provider}-${index}`,
					category: shape.category,
					provider: shape.provider,
					// A resilience row stores variability here, not a score: 0.157 shown
					// as the score would be wrong by a factor of five hundred.
					// A resilience row stores the HRV coefficient of variation here; the
					// readable score is derived from it, so the fixture derives it the
					// same way round rather than inventing two unrelated numbers.
					value:
						shape.category === 'resilience'
							? Number(((40 - resilienceScore(day) * 0.33) / 100).toFixed(3))
							: value,
					qualifier: shape.category === 'recovery' ? STRESS_STATES[step % 4] : null,
					recorded_at: `${isoDay(day)}T${String(hour).padStart(2, '0')}:00:00Z`,
					// Never filled in practice, whatever the schema allows.
					zone_offset: null,
					components:
						shape.category === 'resilience'
							? {
									metric_type: { value: null, qualifier: 'RMSSD' },
									days_counted: { value: 7, qualifier: null },
									resilience_score: { value: resilienceScore(day), qualifier: null }
								}
							: components,
					event_record_id: null,
					data_source_id: null
				});
			}
		}
	}

	return rows.sort((left, right) =>
		String(right.recorded_at).localeCompare(String(left.recorded_at))
	);
};

const SCORES = buildScores();

/** Offset paging with a real count — the one list endpoint that has both. */
export const makeScores = (query: URLSearchParams) => {
	const bound = (raw: string | null, fallback: number) =>
		new Date(raw && raw !== '0' ? raw : fallback).getTime();

	const start = bound(query.get('start_date'), 0);
	const end = bound(query.get('end_date'), Date.now() + 86_400_000);
	const category = query.get('category');

	const matched = SCORES.filter((row) => {
		const at = new Date(String(row.recorded_at)).getTime();
		return at >= start && at < end && (!category || row.category === category);
	});

	const limit = Number(query.get('limit') ?? 50);
	const offset = Number(query.get('offset') ?? 0);
	const data = matched.slice(offset, offset + limit);

	return {
		data,
		pagination: { total_count: matched.length, has_more: offset + data.length < matched.length },
		metadata: { sample_count: data.length }
	};
};

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
		scope: 'daily',
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

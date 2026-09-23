import { ApiError, apiGet } from './api';
import { forget, keep, recall } from './cache';
import { SYNC_WINDOW, type RunFilters } from '$lib/syncs/runs';
import type { SyncRun, SyncRunDetail, SyncRunSummary } from '$lib/syncs/types';

/** Postgres: not time limited, but only historical runs are stored. */
export const fetchSyncHistory = (userId: string, accessToken: string, limit = 50) =>
	apiGet<SyncRun[]>(`/api/v1/users/${userId}/sync/history?limit=${limit}`, accessToken);

/** Redis: every scope, but only the last 24h. */
export const fetchRecentRuns = (userId: string, accessToken: string, limit = 20) =>
	apiGet<SyncRunSummary[]>(`/api/v1/users/${userId}/sync/runs?limit=${limit}`, accessToken);

export type RunWindow = { runs: SyncRunSummary[]; fetchedAt: string };

const TTL_SECONDS = 20;

const windowKey = (filters: RunFilters) => `ow:syncs:${Object.values(filters).join(':')}`;

const PARAM: Record<keyof RunFilters, string> = {
	user: 'user_id',
	provider: 'provider',
	status: 'status',
	source: 'source'
};

/**
 * Every user's runs from the last 24 hours. The endpoint scans every buffer
 * whatever the limit, so one window is kept briefly and paged through here.
 * Filters go to the backend: it applies them before cutting to the limit.
 */
export async function fetchRunWindow(filters: RunFilters, accessToken: string): Promise<RunWindow> {
	const hit = await recall<RunWindow>(windowKey(filters));
	if (hit) return hit;

	const params = new URLSearchParams({ limit: String(SYNC_WINDOW) });
	for (const [key, value] of Object.entries(filters)) {
		if (value) params.set(PARAM[key as keyof RunFilters], value);
	}

	const runs = await apiGet<SyncRunSummary[]>(`/api/v1/sync/runs?${params}`, accessToken);
	return keep(windowKey(filters), { runs, fetchedAt: new Date().toISOString() }, TTL_SECONDS);
}

export const forgetRunWindow = (filters: RunFilters) => forget(windowKey(filters));

/** Postgres. Null for a live run, which is only ever in the 24-hour buffer. */
export async function fetchStoredRun(runKey: string, accessToken: string) {
	try {
		return await apiGet<SyncRunDetail>(
			`/api/v1/sync/history/${encodeURIComponent(runKey)}`,
			accessToken
		);
	} catch (error) {
		if (error instanceof ApiError && error.status === 404) return null;
		throw error;
	}
}

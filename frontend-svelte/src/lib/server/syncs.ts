import { ApiError, apiGet } from './api';
import { keep, recall } from './cache';
import { redis } from './redis';
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

const windowKey = (filters: RunFilters) =>
	`ow:syncs:${filters.user}:${filters.provider}:${filters.status}:${filters.source}`;

/**
 * Every user's runs, newest first — Redis, so the last 24 hours. The endpoint
 * scans every user's buffer on each call whatever the limit, so the window is
 * kept for twenty seconds: paging through it, or coming back to the tab, does
 * not scan again. The filters go to the backend, since it applies them before
 * it cuts to the limit, and a filter done here would search only the window.
 */
export async function fetchRunWindow(filters: RunFilters, accessToken: string): Promise<RunWindow> {
	const hit = await recall<RunWindow>(windowKey(filters));
	if (hit) return hit;

	const params = new URLSearchParams({ limit: String(SYNC_WINDOW) });
	if (filters.user) params.set('user_id', filters.user);
	if (filters.provider) params.set('provider', filters.provider);
	if (filters.status) params.set('status', filters.status);
	if (filters.source) params.set('source', filters.source);

	const runs = await apiGet<SyncRunSummary[]>(`/api/v1/sync/runs?${params}`, accessToken);
	return keep(windowKey(filters), { runs, fetchedAt: new Date().toISOString() }, TTL_SECONDS);
}

/** What the Refresh button does: the next read goes to the backend. */
export const forgetRunWindow = (filters: RunFilters) =>
	redis()
		.del(windowKey(filters))
		.catch(() => {});

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

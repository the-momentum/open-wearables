import { apiGet } from './api';
import type { SyncRun, SyncRunSummary } from '$lib/syncs/types';

/** Postgres: not time limited, but only historical runs are stored. */
export const fetchSyncHistory = (userId: string, accessToken: string, limit = 50) =>
	apiGet<SyncRun[]>(`/api/v1/users/${userId}/sync/history?limit=${limit}`, accessToken);

/** Redis: every scope, but only the last 24h. */
export const fetchRecentRuns = (userId: string, accessToken: string, limit = 20) =>
	apiGet<SyncRunSummary[]>(`/api/v1/users/${userId}/sync/runs?limit=${limit}`, accessToken);

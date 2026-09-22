import { apiGet } from './api';
import type { SystemInfo } from '$lib/dashboard/types';
import type { PaginatedUsers } from '$lib/users/types';

/**
 * The whole dashboard in one response. The backend serves the total data-point
 * count from a Redis cache and falls back to the planner's estimate on a cold
 * one, precisely so this page never pays for a multi-second scan — so nothing
 * here should go looking for a more exact number.
 */
export const fetchSystemInfo = (accessToken: string) =>
	apiGet<SystemInfo>('/api/v1/dashboard/stats', accessToken);

/**
 * The newest few users, sorted by `created_at` — **never** by `last_synced_at`,
 * which the repository resolves with a correlated `max()` subquery evaluated for
 * every user row before the LIMIT. Neither column is indexed, so both scan; on
 * 200k users that is 9ms against 370ms, and 200,000 index searches to return six
 * rows. The old dashboard asked for it on every load.
 *
 * The limit barely moves the cost — the scan and the sort are paid whatever it
 * is, and the per-row connection summary is one index lookup each. Measured on
 * 200k users: 6 rows 8.8ms, 25 rows 7.2ms, 100 rows 7.3ms. So this is a choice
 * about how much list belongs on a dashboard, not about what it costs. The API
 * caps it at 100.
 */
export const fetchNewestUsers = (accessToken: string, limit = 10) =>
	apiGet<PaginatedUsers>(
		`/api/v1/users?page=1&limit=${limit}&sort_by=created_at&sort_order=desc&include=connections`,
		accessToken
	);

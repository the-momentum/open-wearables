import { SYNC_SOURCES } from './source';
import type { SyncRunSummary, SyncStatus } from './types';

/** Runs fetched at once; `/sync/runs` scans every buffer whatever the limit. */
export const SYNC_WINDOW = 500;

/** Mirrors backend `SyncStatus`, for the filter. */
export const SYNC_STATUSES: SyncStatus[] = [
	'in_progress',
	'success',
	'partial',
	'failed',
	'cancelled',
	'skipped',
	'unfinished',
	'stale'
];

export type RunFilters = { user: string; provider: string; status: string; source: string };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Only what the endpoint can match: a non-UUID user is a 422, an unknown status an empty list. */
export function runFilters(params: URLSearchParams): RunFilters {
	const asked = (key: string) => params.get(key)?.trim() ?? '';
	const user = asked('user');
	const status = asked('status');
	const source = asked('source');
	return {
		user: UUID.test(user) ? user.toLowerCase() : '',
		provider: asked('provider'),
		status: SYNC_STATUSES.includes(status as SyncStatus) ? status : '',
		source: SYNC_SOURCES.includes(source) ? source : ''
	};
}

export const filtered = (filters: RunFilters) =>
	Boolean(filters.user || filters.provider || filters.status || filters.source);

/** One page of the window, 1-based, clamped to what exists. */
export function pageOf<T>(runs: T[], page: number, size: number) {
	const pages = Math.max(Math.ceil(runs.length / size), 1);
	const at = Math.min(Math.max(page, 1), pages);
	return { page: at, rows: runs.slice((at - 1) * size, at * size) };
}

/** How a status is drawn in the mix: the tone its badge wears, as a bar shade. */
const SHADE: Record<SyncStatus, string> = {
	success: 'bg-success',
	skipped: 'bg-muted-foreground/30',
	in_progress: 'bg-primary',
	partial: 'bg-warning',
	unfinished: 'bg-warning/70',
	stale: 'bg-warning/45',
	failed: 'bg-danger',
	cancelled: 'bg-border'
};

export function overview(runs: SyncRunSummary[]) {
	const count = (...statuses: SyncStatus[]) =>
		runs.filter((run) => statuses.includes(run.status)).length;

	return {
		running: count('in_progress'),
		failed: count('failed'),
		// Partial and the rest need a look, but are not outright failures.
		attention: count('partial', 'unfinished', 'stale'),
		// "Skipped" is a sync that found nothing new — done, and most of them.
		completed: count('success', 'skipped'),
		users: new Set(runs.map((run) => run.user_id)).size,
		mix: SYNC_STATUSES.map((status) => ({
			key: status,
			value: count(status),
			shade: SHADE[status]
		})).filter((part) => part.value > 0)
	};
}

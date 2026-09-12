export type SyncStatus =
	'in_progress' | 'success' | 'failed' | 'partial' | 'cancelled' | 'skipped' | 'stale';

/** Mirrors backend `SyncRunRecord` — Postgres, unbounded in time, historical runs. */
export type SyncRun = {
	run_key: string;
	user_id: string;
	provider: string;
	source: string;
	scope: 'historical' | 'live';
	status: SyncStatus;
	trace_id: string | null;
	window_start: string | null;
	window_end: string | null;
	started_at: string;
	ended_at: string | null;
	items_inserted: number;
	items_updated: number;
	error: string | null;
};

/** Mirrors backend `SyncRunSummary` — Redis, last 24h, every scope. */
export type SyncRunSummary = {
	run_id: string;
	user_id: string;
	provider: string;
	source: string;
	stage: string;
	status: string;
	message: string | null;
	progress: number | null;
	items_processed: number | null;
	items_total: number | null;
	// Optional: the backend has them in event metadata but the summary schema
	// drops them, so today they only reach us inside `message`.
	items_inserted?: number | null;
	items_updated?: number | null;
	error: string | null;
	started_at: string | null;
	ended_at: string | null;
	last_update: string;
};

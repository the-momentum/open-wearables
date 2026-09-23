export type SyncStatus =
	| 'in_progress'
	| 'success'
	| 'failed'
	| 'partial'
	| 'cancelled'
	| 'skipped'
	| 'unfinished'
	| 'stale';

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
	status: SyncStatus;
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

/** Mirrors `SyncRunDataTypeRecord`: one data type inside a stored run. */
export type SyncDataType = {
	data_type: string;
	kind: string;
	status: SyncStatus;
	native_type: string | null;
	reported_records: number | null;
	items_inserted: number;
	items_updated: number;
	covered_start: string | null;
	covered_end: string | null;
	error_code: string | null;
	error: string | null;
	attempt: number;
};

/** Mirrors `SyncRunDetail`: a stored run and what it did per data type. */
export type SyncRunDetail = SyncRun & { data_types: SyncDataType[] };

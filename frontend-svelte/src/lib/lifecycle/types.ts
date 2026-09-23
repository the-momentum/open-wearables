/** Mirrors backend `ArchivalSettingRead`. Null switches the stage off. */
export type ArchivalSettings = {
	archive_after_days: number | null;
	delete_after_days: number | null;
};

/**
 * Mirrors `StorageEstimate`, less the `_pretty` strings: the page formats every
 * size itself, so the figure for today and the projection's first point are
 * the same number by construction.
 */
export type StorageEstimate = {
	live_data_bytes: number;
	live_index_bytes: number;
	archive_data_bytes: number;
	archive_index_bytes: number;
	other_tables_bytes: number;
	total_bytes: number;
	/** From `pg_stat_user_tables.n_live_tup` — a planner statistic, not a count. */
	live_row_count: number;
	archive_row_count: number;
	live_data_span_days: number;
};

export type Lifecycle = { settings: ArchivalSettings; storage: StorageEstimate };

/** What the form edits and the projection draws: days, or null for off. */
export type Policy = { archive: number | null; retain: number | null };

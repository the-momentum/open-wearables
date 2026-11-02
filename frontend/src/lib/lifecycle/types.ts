/** Mirrors backend `ArchivalSettingRead`. */
export type ArchivalSettings = {
	rollup_enabled: boolean;
	/** Null keeps samples forever. */
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
	/** The rolled-up day and session tables, plus the archive they replace. */
	aggregate_data_bytes: number;
	aggregate_index_bytes: number;
	other_tables_bytes: number;
	total_bytes: number;
	/** From `pg_stat_user_tables.n_live_tup` - a planner statistic, not a count. */
	live_row_count: number;
	aggregate_row_count: number;
	live_data_span_days: number;
};

export type Lifecycle = { settings: ArchivalSettings; storage: StorageEstimate };

/** What the form edits and the projection draws: rollup on or off, deletion in days or null for off. */
export type Policy = { rollup: boolean; retain: number | null };

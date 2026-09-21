/** Mirrors backend `ScoreComponent`: one constituent of a score. */
export type ScoreComponent = { value: number | null; qualifier: string | null };

/**
 * Mirrors backend `HealthScoreResponse`. There is no `source` here, unlike the
 * event endpoints — a score carries its provider and a bare `data_source_id`,
 * so no device can be named.
 *
 * `zone_offset` is part of the contract but no provider has ever filled it, so
 * every reading here is read as UTC.
 */
export type HealthScore = {
	id: string;
	category: string;
	provider: string | null;
	value: number | null;
	qualifier: string | null;
	recorded_at: string;
	zone_offset: string | null;
	components: Record<string, ScoreComponent> | null;
	/** The sleep session or workout this scores. Null for a whole-day score. */
	event_record_id: string | null;
};

export type ScorePage = {
	data: HealthScore[];
	pagination: { total_count: number; has_more: boolean };
};

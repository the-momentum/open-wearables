import type { SourceMetadata } from '$lib/events/types';

/** Mirrors backend `SleepStageType`. */
export type StageName = 'awake' | 'rem' | 'light' | 'deep' | 'sleeping' | 'in_bed' | 'unknown';

/** Mirrors `SleepStage`: one continuous interval from the stages JSONB. */
export type StageInterval = { stage: StageName; start_time: string; end_time: string };

/** Mirrors `SleepStagesSummary` — minutes per stage, which most providers send. */
export type StageMinutes = {
	awake_minutes: number | null;
	light_minutes: number | null;
	deep_minutes: number | null;
	rem_minutes: number | null;
};

/**
 * Mirrors backend `SleepSession`. `sleep_stage_intervals` arrives only with
 * `include=stages`, and only from a provider that reports them at all.
 */
export type SleepSession = {
	id: string;
	start_time: string;
	end_time: string;
	zone_offset: string | null;
	source: SourceMetadata;
	duration_seconds: number;
	sleep_duration_seconds: number | null;
	time_in_bed_seconds: number | null;
	efficiency_percent: number | null;
	stages: StageMinutes | null;
	sleep_stage_intervals: StageInterval[] | null;
	is_nap: boolean;
};

export type SleepPage = {
	data: SleepSession[];
	pagination: {
		next_cursor: string | null;
		previous_cursor: string | null;
		has_more: boolean;
		total_count: number | null;
	};
};

import type { SourceMetadata } from '$lib/events/types';

/**
 * Mirrors backend `MenstrualCycleRecord`. The columns are the unified ones —
 * Garmin's MCT fills them today, and any provider that sends cycles writes into
 * the same shape.
 */
export type Cycle = {
	id: string;
	start_time: string;
	end_time: string;
	zone_offset: string | null;
	source: SourceMetadata;
	/** The provider's own code for the phase; the readable name is the type. */
	current_phase: number | null;
	current_phase_type: string | null;
	day_in_cycle: number | null;
	cycle_length: number | null;
	predicted_cycle_length: number | null;
	is_predicted_cycle: boolean | null;
	period_length: number | null;
	length_of_current_phase: number | null;
	days_until_next_phase: number | null;
	fertile_window_start: number | null;
	length_of_fertile_window: number | null;
	last_updated_at: string | null;
	/** Whether the person told the app, rather than the app inferring it. */
	has_specified_cycle_length: boolean | null;
	has_specified_period_length: boolean | null;
	pregnancy_snapshot: Record<string, unknown>[] | null;
};

export type CyclePage = {
	data: Cycle[];
	pagination: {
		next_cursor: string | null;
		previous_cursor: string | null;
		has_more: boolean;
		total_count: number | null;
	};
};

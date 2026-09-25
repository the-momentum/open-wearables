import type { SourceMetadata } from '$lib/events/types';

/** Mirrors backend `HRZones` / `PowerZones` (app/schemas/model_crud/activities/zones.py). */
export type HRZone = { zone: number; seconds: number; max_bpm: number | null };
export type HRZones = { zones: HRZone[]; max_hr: number | null; threshold_hr: number | null };

export type PowerZone = { zone: number; seconds: number; max_watts: number | null };
export type PowerZones = { zones: PowerZone[]; ftp_watts: number | null };

/**
 * Mirrors backend `Workout`. Almost everything is nullable because no provider
 * fills every field — see each provider's `WORKOUT_FIELDS` in the coverage matrix.
 */
export type Workout = {
	id: string;
	type: string;
	name: string | null;
	start_time: string;
	end_time: string;
	zone_offset: string | null;
	duration_seconds: number | null;
	source: SourceMetadata;
	entry_source: string | null;
	intensity: string | null;
	calories_kcal: number | null;
	distance_meters: number | null;
	avg_heart_rate_bpm: number | null;
	max_heart_rate_bpm: number | null;
	heart_rate_min: number | null;
	avg_pace_sec_per_km: number | null;
	elevation_gain_meters: number | null;
	steps_count: number | null;
	/** Unit differs per provider — Suunto stores km/h, the rest m/s. Do not format. */
	average_speed: number | null;
	max_speed: number | null;
	average_cadence: number | null;
	average_watts: number | null;
	max_watts: number | null;
	moving_time_seconds: number | null;
	elev_high: number | null;
	elev_low: number | null;
	hr_zones: HRZones | null;
	power_zones: PowerZones | null;
	segments: Record<string, unknown>[] | null;
};

/** Mirrors `PaginatedResponse[Workout]`; the list is cursor paged, not offset. */
export type WorkoutPage = {
	data: Workout[];
	pagination: {
		next_cursor: string | null;
		previous_cursor: string | null;
		has_more: boolean;
		total_count: number | null;
	};
};

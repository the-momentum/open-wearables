import type { WorkoutSource } from '$lib/workouts/types';

/** Mirrors backend `IntensityMinutes` — minutes in each heart-rate band. */
export type IntensityMinutes = {
	light: number | null;
	moderate: number | null;
	vigorous: number | null;
};

/** Mirrors `HeartRateStats`. */
export type HeartRateStats = {
	avg_bpm: number | null;
	max_bpm: number | null;
	min_bpm: number | null;
};

/**
 * Mirrors backend `ActivitySummary`: one day, aggregated from the time series.
 * The endpoint already keeps the highest-priority source per date, so there is
 * one row per day and no id — a day is not a record anyone can delete.
 */
export type ActivityDay = {
	date: string;
	source: WorkoutSource;
	steps: number | null;
	distance_meters: number | null;
	floors_climbed: number | null;
	elevation_meters: number | null;
	active_calories_kcal: number | null;
	total_calories_kcal: number | null;
	active_minutes: number | null;
	sedentary_minutes: number | null;
	intensity_minutes: IntensityMinutes | null;
	heart_rate: HeartRateStats | null;
};

export type ActivityPage = {
	data: ActivityDay[];
	pagination: {
		next_cursor: string | null;
		previous_cursor: string | null;
		has_more: boolean;
		total_count: number | null;
	};
};

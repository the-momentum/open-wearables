import type { WorkoutSource } from '$lib/workouts/types';

/** Mirrors backend `BodySlowChanging`: the latest reading of each. */
export type SlowChanging = {
	weight_kg: number | null;
	height_cm: number | null;
	body_fat_percent: number | null;
	muscle_mass_kg: number | null;
	bmi: number | null;
	age: number | null;
};

/** Mirrors `BodyAveraged`. Vitals mean little as one reading, so these are means. */
export type Averaged = {
	period_days: number;
	resting_heart_rate_bpm: number | null;
	avg_hrv_sdnn_ms: number | null;
	avg_hrv_rmssd_ms: number | null;
	period_start: string;
	period_end: string;
};

export type BloodPressure = { systolic: number | null; diastolic: number | null };

/**
 * Mirrors `BodyLatest`. Every field here is withheld unless it was measured
 * recently, so a null means "nothing fresh", not "never measured".
 */
export type Latest = {
	body_temperature_celsius: number | null;
	body_temperature_measured_at: string | null;
	skin_temperature_celsius: number | null;
	skin_temperature_measured_at: string | null;
	blood_pressure: BloodPressure | null;
	blood_pressure_measured_at: string | null;
};

/** Mirrors `BodySummary`. The endpoint answers null when the user has no body data. */
export type BodySummary = {
	source: WorkoutSource;
	slow_changing: SlowChanging;
	averaged: Averaged;
	latest: Latest;
};

export type Range = [number, number];

/** Mirrors backend `WorkoutConfig`. Explicit dates override the month count. */
export type WorkoutConfig = {
	count: number;
	/** Null draws from every type. */
	workout_types: string[] | null;
	duration_min_minutes: number;
	duration_max_minutes: number;
	hr_min_range: Range;
	hr_max_range: Range;
	steps_range: Range;
	date_range_months: number;
	date_from?: string | null;
	date_to?: string | null;
};

export type StageDistribution = {
	deep_pct_range: Range;
	rem_pct_range: Range;
	awake_pct_range: Range;
};

/** Mirrors `SleepConfig`. A named stage profile wins over the distribution. */
export type SleepConfig = {
	count: number;
	duration_min_minutes: number;
	duration_max_minutes: number;
	nap_chance_pct: number;
	weekend_catchup: boolean;
	date_range_months: number;
	date_from?: string | null;
	date_to?: string | null;
	stage_profile: string | null;
	stage_distribution: StageDistribution;
};

/** Mirrors `TimeSeriesConfig`. An empty list emits no continuous series. */
export type TimeSeriesConfig = {
	enabled_types: string[];
	include_blood_pressure: boolean;
	date_range_months: number;
	date_from?: string | null;
	date_to?: string | null;
};

/** Mirrors `SeedProfileConfig`. */
export type SeedProfile = {
	preset: string | null;
	generate_workouts: boolean;
	generate_sleep: boolean;
	generate_time_series: boolean;
	/** Null picks at random; a list is cut to `num_connections` in its order. */
	providers: string[] | null;
	num_connections: number;
	workout_config: WorkoutConfig;
	sleep_config: SleepConfig;
	time_series_config: TimeSeriesConfig;
};

export type SeedPreset = { id: string; label: string; description: string; profile: SeedProfile };

export type SleepProfile = {
	id: string;
	label: string;
	description: string;
	distribution: StageDistribution;
};

export type SeedRequest = { num_users: number; profile: SeedProfile; random_seed: number | null };

/** Mirrors `SeedDataResponse`. The seed is resolved before dispatch, so it is known at once. */
export type SeedResponse = { task_id: string; status: string; seed_used: number | null };

/** Mirrors backend `UserDataSummaryResponse`. */
export type ProviderDataCount = {
	provider: string;
	data_points: number;
	series_counts: Record<string, number>;
	workout_count: number;
	sleep_count: number;
};

export type DataSummary = {
	total_data_points: number;
	total_workouts: number;
	total_sleep_events: number;
	series_type_counts: Record<string, number>;
	workout_type_counts: Record<string, number>;
	by_provider: ProviderDataCount[];
	has_womens_health_data: boolean;
};

/** Mirrors `UserDataTimelineResponse`. Sparse: empty buckets are omitted. */
export type TimelineSeries = {
	key: string;
	metric: string;
	/** `[bucket_start, count]`, chronological. */
	buckets: [string, number][];
};

export type DataTimeline = {
	bucket: 'day' | 'week';
	group_by: 'provider' | 'series_type';
	series: TimelineSeries[];
};

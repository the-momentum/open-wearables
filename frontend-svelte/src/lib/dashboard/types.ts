/** Mirrors backend `SystemInfoResponse` — the whole dashboard, in one response. */
export type SystemInfo = {
	total_users: { count: number };
	active_conn: { count: number };
	/**
	 * Mirrors `DataPointsInfo`. Both figures are **approximate**: the live count
	 * is served from a Redis cache and falls back to the planner's `reltuples`
	 * on a cold one, and the archive count is always from planner statistics.
	 */
	data_points: { count: number; archived: number };
	event_records: { count: number; workouts: number; sleep: number; menstrual_cycles: number };
	connections_coverage: {
		users_with_active: number;
		users_with_multi_active: number;
		/** The backend caps this at six. */
		top_providers: { provider: string; count: number }[];
	};
};

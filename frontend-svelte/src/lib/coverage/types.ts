/** Mirrors backend `CoverageResponse` — what each provider can deliver, in code. */
export type Coverage = {
	providers: string[];
	timeseries: { name: string; metrics: CoverageMetric[] }[];
	workout_fields: CoverageField[];
	sleep_fields: CoverageField[];
	menstrual_cycle_fields: CoverageField[];
	health_scores: CoverageScore[];
};

export type CoverageField = { code: string; providers: string[] };
export type CoverageMetric = CoverageField & { unit: string; description: string };
export type CoverageScore = CoverageField & { description: string };

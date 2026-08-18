import { apiClient } from '../client';
import { API_ENDPOINTS } from '../config';

export interface TimeseriesMetric {
  code: string;
  unit: string;
  providers: string[];
}

export interface TimeseriesCategory {
  name: string;
  metrics: TimeseriesMetric[];
}

export interface WorkoutField {
  code: string;
  providers: string[];
}

export interface SleepField {
  code: string;
  providers: string[];
}

export interface MenstrualCycleField {
  code: string;
  providers: string[];
}

export interface HealthScore {
  code: string;
  providers: string[];
}

export interface CoverageResponse {
  providers: string[];
  timeseries: TimeseriesCategory[];
  workout_fields: WorkoutField[];
  sleep_fields: SleepField[];
  menstrual_cycle_fields: MenstrualCycleField[];
  health_scores: HealthScore[];
}

export const metaService = {
  async getCoverage(): Promise<CoverageResponse> {
    return apiClient.get<CoverageResponse>(API_ENDPOINTS.coverage);
  },
};

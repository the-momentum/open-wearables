import { apiClient } from '../client';
import { ApiError } from '../../errors/api-error';
import { API_ENDPOINTS } from '../config';

// Types

export interface WorkoutConfig {
  count: number;
  workout_types: string[] | null;
  duration_min_minutes: number;
  duration_max_minutes: number;
  hr_min_range: [number, number];
  hr_max_range: [number, number];
  steps_range: [number, number];
  time_series_chance_pct: number;
  date_range_months: number;
  date_from: string | null;
  date_to: string | null;
}

export interface SleepStageDistribution {
  deep_pct_range: [number, number];
  rem_pct_range: [number, number];
  awake_pct_range: [number, number];
}

export interface SleepStageProfile {
  id: string;
  label: string;
  description: string;
  distribution: SleepStageDistribution;
}

export interface SleepConfig {
  count: number;
  duration_min_minutes: number;
  duration_max_minutes: number;
  nap_chance_pct: number;
  weekend_catchup: boolean;
  date_range_months: number;
  date_from: string | null;
  date_to: string | null;
  stage_profile: string | null;
  stage_distribution: SleepStageDistribution;
}

export interface SeedProfileConfig {
  preset: string | null;
  generate_workouts: boolean;
  generate_sleep: boolean;
  generate_time_series: boolean;
  providers: string[] | null;
  num_connections: number;
  workout_config: WorkoutConfig;
  sleep_config: SleepConfig;
}

export interface SeedDataRequest {
  num_users: number;
  profile: SeedProfileConfig;
  random_seed: number | null;
}

export interface SeedDataResponse {
  task_id: string;
  status: string;
  seed_used: number | null;
}

export interface SeedPreset {
  id: string;
  label: string;
  description: string;
  profile: SeedProfileConfig;
}

// Service

export const seedDataService = {
  async generate(data: SeedDataRequest): Promise<SeedDataResponse> {
    try {
      return await apiClient.post<SeedDataResponse>(
        API_ENDPOINTS.seedGenerate,
        data
      );
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw ApiError.networkError((error as Error).message);
    }
  },

  async getPresets(): Promise<SeedPreset[]> {
    try {
      return await apiClient.get<SeedPreset[]>(API_ENDPOINTS.seedPresets);
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw ApiError.networkError((error as Error).message);
    }
  },

  async getSleepStageProfiles(): Promise<SleepStageProfile[]> {
    try {
      return await apiClient.get<SleepStageProfile[]>(
        API_ENDPOINTS.seedSleepProfiles
      );
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw ApiError.networkError((error as Error).message);
    }
  },
};

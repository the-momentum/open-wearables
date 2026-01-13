import { apiClient } from '../client';
import { API_ENDPOINTS } from '../config';
import type {
  UserConnection,
  EventRecordResponse,
  HealthDataParams,
  PaginatedResponse,
  TimeSeriesParams,
  TimeSeriesSample,
  SyncResponse,
  GarminBackfillStatus,
  ActivitySummary,
  SleepSummary,
  BodySummary,
  RecoverySummary,
} from '../types';

export interface WorkoutsParams {
  start_date?: string;
  end_date?: string;
  limit?: number;
  offset?: number;
  sort_order?: 'asc' | 'desc';
  workout_type?: string;
  source_name?: string;
  min_duration?: number;
  max_duration?: number;
  sort_by?:
    | 'start_datetime'
    | 'end_datetime'
    | 'duration_seconds'
    | 'type'
    | 'source_name';
  [key: string]: string | number | undefined;
}

export interface SummaryParams {
  start_date: string; // ISO date string (e.g., "2025-01-01T00:00:00Z")
  end_date: string; // ISO date string
  cursor?: string;
  limit?: number; // 1-100, default 50
  [key: string]: string | number | undefined;
}

export const healthService = {
  /**
   * Synchronize workouts/exercises/activities from fitness provider API for a specific user
   */
  async synchronizeProvider(
    provider: string,
    userId: string
  ): Promise<SyncResponse> {
    return apiClient.post<SyncResponse>(
      API_ENDPOINTS.providerSynchronization(provider, userId)
    );
  },

  /**
   * Get Garmin backfill status for a user
   */
  async getGarminBackfillStatus(userId: string): Promise<GarminBackfillStatus> {
    return apiClient.get<GarminBackfillStatus>(
      `/api/v1/providers/garmin/users/${userId}/backfill-status`
    );
  },

  /**
   * Get user connections for a user
   */
  async getUserConnections(userId: string): Promise<UserConnection[]> {
    return apiClient.get<UserConnection[]>(
      API_ENDPOINTS.userConnections(userId)
    );
  },

  /**
   * Get workouts for a user
   */
  async getWorkouts(
    userId: string,
    params?: HealthDataParams
  ): Promise<PaginatedResponse<EventRecordResponse>> {
    return apiClient.get<PaginatedResponse<EventRecordResponse>>(
      API_ENDPOINTS.userWorkouts(userId),
      {
        params,
      }
    );
  },

  /**
   * Get activity summaries for a date range
   */
  async getActivitySummaries(
    userId: string,
    params: SummaryParams
  ): Promise<PaginatedResponse<ActivitySummary>> {
    return apiClient.get<PaginatedResponse<ActivitySummary>>(
      API_ENDPOINTS.userActivitySummary(userId),
      { params }
    );
  },

  /**
   * Get sleep summaries for a date range
   */
  async getSleepSummaries(
    userId: string,
    params: SummaryParams
  ): Promise<PaginatedResponse<SleepSummary>> {
    return apiClient.get<PaginatedResponse<SleepSummary>>(
      API_ENDPOINTS.userSleepSummary(userId),
      { params }
    );
  },

  /**
   * Get body composition and vitals summaries for a date range
   */
  async getBodySummaries(
    userId: string,
    params: SummaryParams
  ): Promise<PaginatedResponse<BodySummary>> {
    return apiClient.get<PaginatedResponse<BodySummary>>(
      API_ENDPOINTS.userBodySummary(userId),
      { params }
    );
  },

  /**
   * Get recovery summaries for a date range
   */
  async getRecoverySummaries(
    userId: string,
    params: SummaryParams
  ): Promise<PaginatedResponse<RecoverySummary>> {
    return apiClient.get<PaginatedResponse<RecoverySummary>>(
      API_ENDPOINTS.userRecoverySummary(userId),
      { params }
    );
  },

  async syncUserData(
    userId: string
  ): Promise<{ message: string; jobId: string }> {
    return apiClient.post<{ message: string; jobId: string }>(
      `/v1/users/${userId}/sync`,
      {}
    );
  },

  async getTimeSeries(
    userId: string,
    params: TimeSeriesParams
  ): Promise<PaginatedResponse<TimeSeriesSample>> {
    return apiClient.get<PaginatedResponse<TimeSeriesSample>>(
      `/api/v1/users/${userId}/timeseries`,
      {
        params,
      }
    );
  },
};

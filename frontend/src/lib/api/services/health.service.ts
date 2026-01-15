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

  async getSleepData(userId: string, days: number = 7): Promise<SleepData[]> {
    return apiClient.get<SleepData[]>(`/v1/users/${userId}/sleep`, {
      params: { days },
    });
  },

  async getActivityData(
    userId: string,
    days: number = 7
  ): Promise<ActivityData[]> {
    return apiClient.get<ActivityData[]>(`/v1/users/${userId}/activity`, {
      params: { days },
    });
  },

  async getHealthSummary(
    userId: string,
    period: string = '7d'
  ): Promise<HealthDataSummary> {
    return apiClient.get<HealthDataSummary>(
      `/v1/users/${userId}/health-summary`,
      {
        params: { period },
      }
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

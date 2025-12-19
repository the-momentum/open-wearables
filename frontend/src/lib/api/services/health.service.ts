import { apiClient } from '../client';
import { API_ENDPOINTS } from '../config';
import type {
  WorkoutResponse,
  UserConnection,
  HeartRateSampleResponse,
  EventRecordResponse,
  HealthDataParams,
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
  async synchronizeProvider(provider: string, userId: string): Promise<void> {
    return apiClient.post<void>(
      API_ENDPOINTS.providerSynchronization(provider, userId)
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
   * Get heart rate data for a user
   */
  async getHeartRate(userId: string): Promise<HeartRateSampleResponse[]> {
    return apiClient.get<HeartRateSampleResponse[]>(
      API_ENDPOINTS.userHeartRate(userId)
    );
  },

  /**
   * Get workouts for a user
   */
  async getWorkouts(
    userId: string,
    deviceId: string,
    days: number = 7
  ): Promise<HeartRateData[]> {
    const end = new Date();
    const start = new Date(end);
    start.setDate(end.getDate() - days);

    const samples = await apiClient.get<HeartRateSampleResponse[]>(
      `/v1/users/${userId}/heart-rate`,
      {
        params: {
          start_datetime: start.toISOString(),
          end_datetime: end.toISOString(),
          device_id: deviceId,
        },
      }
    );

    return samples.map((sample) => ({
      id: sample.id,
      userId,
      timestamp: sample.recorded_at,
      value: Number(sample.value),
      source: sample.device_id ?? 'unknown',
    }));
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

  async getHeartRateList(
    userId: string,
    params?: HealthDataParams
  ): Promise<HeartRateSampleResponse[]> {
    return apiClient.get<HeartRateSampleResponse[]>(
      `/v1/users/${userId}/heart-rate`,
      { params }
    );
  },

  async getWorkouts(
    userId: string,
    params?: HealthDataParams
  ): Promise<EventRecordResponse[]> {
    return apiClient.get<EventRecordResponse[]>(
      API_ENDPOINTS.userWorkouts(userId),
      {
        params,
      }
    );
  },
};

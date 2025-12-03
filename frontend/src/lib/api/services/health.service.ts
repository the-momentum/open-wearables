import { apiClient } from '../client';
import { API_ENDPOINTS } from '../config';
import type { WorkoutStatisticResponse, WorkoutResponse, UserConnection } from '../types';

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
   * Get user connections for a user
   */
  async getUserConnections(userId: string): Promise<UserConnection[]> {
    return apiClient.get<UserConnection[]>(API_ENDPOINTS.userConnections(userId));
  },

  /**
   * Get heart rate data for a user
   */
  async getHeartRate(userId: string): Promise<WorkoutStatisticResponse[]> {
    return apiClient.get<WorkoutStatisticResponse[]>(
      API_ENDPOINTS.userHeartRate(userId)
    );
  },

  /**
   * Get workouts for a user
   */
  async getWorkouts(
    userId: string,
    params?: WorkoutsParams
  ): Promise<WorkoutResponse[]> {
    return apiClient.get<WorkoutResponse[]>(
      API_ENDPOINTS.userWorkouts(userId),
      { params }
    );
  },
};

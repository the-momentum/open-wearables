import { apiClient } from '../client';
import type {
  HeartRateData,
  SleepData,
  ActivityData,
  HealthDataSummary,
  Provider,
  UserConnection,
} from '../types';

export const healthService = {
  async getProviders(): Promise<Provider[]> {
    return apiClient.get<Provider[]>('/v1/providers');
  },

  async getUserConnections(userId: string): Promise<UserConnection[]> {
    return apiClient.get<UserConnection[]>(`/v1/users/${userId}/connections`);
  },

  async generateConnectionLink(
    userId: string,
    providerId: string
  ): Promise<{ url: string; expiresAt: string }> {
    return apiClient.post<{ url: string; expiresAt: string }>(
      `/v1/users/${userId}/connections/generate-link`,
      { providerId }
    );
  },

  async disconnectProvider(
    userId: string,
    connectionId: string
  ): Promise<void> {
    return apiClient.delete<void>(
      `/v1/users/${userId}/connections/${connectionId}`
    );
  },

  async getHeartRateData(
    userId: string,
    days: number = 7
  ): Promise<HeartRateData[]> {
    return apiClient.get<HeartRateData[]>(`/v1/users/${userId}/heart-rate`, {
      params: { days },
    });
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
};

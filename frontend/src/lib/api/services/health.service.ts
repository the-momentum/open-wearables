import { apiClient } from '../client';
import type {
  HeartRateData,
  SleepData,
  ActivityData,
  HealthDataSummary,
  Provider,
  UserConnection,
} from '../types';
import {
  generateHeartRateData,
  generateSleepData,
  generateActivityData,
  generateHealthSummary,
} from '@/data/mock/health-data';
import { availableProviders, mockUserConnections } from '@/data/mock/providers';

const USE_MOCK = import.meta.env.VITE_USE_MOCK_API === 'true';

// Helper to simulate API delay
const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export const healthService = {
  // Get available providers
  async getProviders(): Promise<Provider[]> {
    if (USE_MOCK) {
      await delay(200);
      return availableProviders;
    }
    return await apiClient.get<Provider[]>('/v1/providers');
  },

  // Get user connections
  async getUserConnections(userId: string): Promise<UserConnection[]> {
    if (USE_MOCK) {
      await delay(300);
      return mockUserConnections[userId] || [];
    }
    return await apiClient.get<UserConnection[]>(
      `/v1/users/${userId}/connections`
    );
  },

  // Generate connection link
  async generateConnectionLink(
    userId: string,
    providerId: string
  ): Promise<{ url: string; expiresAt: string }> {
    if (USE_MOCK) {
      await delay(400);
      const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      return {
        url: `${baseUrl}/connect/${providerId}?user=${userId}&token=${Math.random().toString(36).substring(7)}`,
        expiresAt: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
      };
    }
    return await apiClient.post<{ url: string; expiresAt: string }>(
      `/v1/users/${userId}/connections/generate-link`,
      { providerId }
    );
  },

  // Disconnect provider
  async disconnectProvider(
    userId: string,
    connectionId: string
  ): Promise<void> {
    if (USE_MOCK) {
      await delay(300);
      const connections = mockUserConnections[userId];
      if (connections) {
        const connection = connections.find((c) => c.id === connectionId);
        if (connection) {
          connection.status = 'disconnected';
        }
      }
      return;
    }
    await apiClient.delete(`/v1/users/${userId}/connections/${connectionId}`);
  },

  // Get heart rate data
  async getHeartRateData(
    userId: string,
    days: number = 7
  ): Promise<HeartRateData[]> {
    if (USE_MOCK) {
      await delay(400);
      return generateHeartRateData(userId).slice(-days * 24);
    }
    return await apiClient.get<HeartRateData[]>(
      `/v1/users/${userId}/heart-rate`,
      {
        params: { days },
      }
    );
  },

  // Get sleep data
  async getSleepData(userId: string, days: number = 7): Promise<SleepData[]> {
    if (USE_MOCK) {
      await delay(400);
      return generateSleepData(userId).slice(-days);
    }
    return await apiClient.get<SleepData[]>(`/v1/users/${userId}/sleep`, {
      params: { days },
    });
  },

  // Get activity data
  async getActivityData(
    userId: string,
    days: number = 7
  ): Promise<ActivityData[]> {
    if (USE_MOCK) {
      await delay(400);
      return generateActivityData(userId).slice(-days);
    }
    return await apiClient.get<ActivityData[]>(`/v1/users/${userId}/activity`, {
      params: { days },
    });
  },

  // Get health summary
  async getHealthSummary(
    userId: string,
    period: string = '7d'
  ): Promise<HealthDataSummary> {
    if (USE_MOCK) {
      await delay(500);
      return generateHealthSummary(userId);
    }
    return await apiClient.get<HealthDataSummary>(
      `/v1/users/${userId}/health-summary`,
      {
        params: { period },
      }
    );
  },

  // Sync user data (trigger manual sync)
  async syncUserData(
    userId: string
  ): Promise<{ message: string; jobId: string }> {
    if (USE_MOCK) {
      await delay(600);
      return {
        message: 'Sync initiated successfully',
        jobId: `job-${Date.now()}`,
      };
    }
    return await apiClient.post<{ message: string; jobId: string }>(
      `/v1/users/${userId}/sync`,
      {}
    );
  },
};

// Dashboard API service

import { apiClient } from '../client';
import { API_ENDPOINTS } from '../config';
import type {
  DashboardStats,
  ApiCallsDataPoint,
  DataPointsDataPoint,
  AutomationTriggersDataPoint,
  TriggersByTypeDataPoint,
} from '../types';
import {
  mockDashboardStats,
  mockApiCallsData,
  mockDataPointsData,
  mockAutomationTriggersData,
  mockTriggersByTypeData,
} from '../../../data/mock/dashboard';

const USE_MOCK = import.meta.env.VITE_USE_MOCK_API === 'true';

// Mock dashboard service
const mockDashboardService = {
  async getStats(): Promise<DashboardStats> {
    await delay(400);
    return mockDashboardStats;
  },

  async getApiCallsData(): Promise<ApiCallsDataPoint[]> {
    await delay(500);
    return mockApiCallsData;
  },

  async getDataPointsData(): Promise<DataPointsDataPoint[]> {
    await delay(500);
    return mockDataPointsData;
  },

  async getAutomationTriggersData(): Promise<AutomationTriggersDataPoint[]> {
    await delay(500);
    return mockAutomationTriggersData;
  },

  async getTriggersByTypeData(): Promise<TriggersByTypeDataPoint[]> {
    await delay(400);
    return mockTriggersByTypeData;
  },
};

// Real dashboard service
const realDashboardService = {
  async getStats(): Promise<DashboardStats> {
    return apiClient.get<DashboardStats>(API_ENDPOINTS.dashboardStats);
  },

  async getApiCallsData(timeRange?: string): Promise<ApiCallsDataPoint[]> {
    const params = new URLSearchParams();
    if (timeRange) params.append('timeRange', timeRange);

    const endpoint = params.toString()
      ? `${API_ENDPOINTS.dashboardCharts}/api-calls?${params}`
      : `${API_ENDPOINTS.dashboardCharts}/api-calls`;

    return apiClient.get<ApiCallsDataPoint[]>(endpoint);
  },

  async getDataPointsData(timeRange?: string): Promise<DataPointsDataPoint[]> {
    const params = new URLSearchParams();
    if (timeRange) params.append('timeRange', timeRange);

    const endpoint = params.toString()
      ? `${API_ENDPOINTS.dashboardCharts}/data-points?${params}`
      : `${API_ENDPOINTS.dashboardCharts}/data-points`;

    return apiClient.get<DataPointsDataPoint[]>(endpoint);
  },

  async getAutomationTriggersData(
    timeRange?: string
  ): Promise<AutomationTriggersDataPoint[]> {
    const params = new URLSearchParams();
    if (timeRange) params.append('timeRange', timeRange);

    const endpoint = params.toString()
      ? `${API_ENDPOINTS.dashboardCharts}/automation-triggers?${params}`
      : `${API_ENDPOINTS.dashboardCharts}/automation-triggers`;

    return apiClient.get<AutomationTriggersDataPoint[]>(endpoint);
  },

  async getTriggersByTypeData(): Promise<TriggersByTypeDataPoint[]> {
    return apiClient.get<TriggersByTypeDataPoint[]>(
      `${API_ENDPOINTS.dashboardCharts}/triggers-by-type`
    );
  },
};

export const dashboardService = USE_MOCK
  ? mockDashboardService
  : realDashboardService;

// Utility function
function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

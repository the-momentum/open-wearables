import { apiClient } from '../client';
import { API_ENDPOINTS } from '../config';
import type {
  DashboardStats,
  ApiCallsDataPoint,
  DataPointsDataPoint,
  AutomationTriggersDataPoint,
  TriggersByTypeDataPoint,
} from '../types';

export const dashboardService = {
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

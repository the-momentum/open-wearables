// Dashboard data hooks

import { useQuery } from '@tanstack/react-query';
import { dashboardService } from '../../lib/api';
import { queryKeys } from '../../lib/query/keys';

/**
 * Fetch dashboard stats
 */
export function useDashboardStats() {
  return useQuery({
    queryKey: queryKeys.dashboard.stats(),
    queryFn: () => dashboardService.getStats(),
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
}

/**
 * Fetch API calls chart data
 */
export function useApiCallsData(timeRange?: string) {
  return useQuery({
    queryKey: queryKeys.dashboard.charts(timeRange),
    queryFn: () => dashboardService.getApiCallsData(timeRange),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Fetch data points chart data
 */
export function useDataPointsData(timeRange?: string) {
  return useQuery({
    queryKey: [...queryKeys.dashboard.charts(timeRange), 'dataPoints'],
    queryFn: () => dashboardService.getDataPointsData(timeRange),
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Fetch automation triggers chart data
 */
export function useAutomationTriggersData(timeRange?: string) {
  return useQuery({
    queryKey: [...queryKeys.dashboard.charts(timeRange), 'automationTriggers'],
    queryFn: () => dashboardService.getAutomationTriggersData(timeRange),
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Fetch triggers by type chart data
 */
export function useTriggersByTypeData() {
  return useQuery({
    queryKey: [...queryKeys.dashboard.charts(), 'triggersByType'],
    queryFn: () => dashboardService.getTriggersByTypeData(),
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

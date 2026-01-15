import { useMutation, useQuery } from '@tanstack/react-query';
import {
  healthService,
  type WorkoutsParams,
  type SummaryParams,
} from '@/lib/api/services/health.service';
import type { TimeSeriesParams, SleepSessionsParams } from '@/lib/api/types';
import { queryKeys } from '@/lib/query/keys';
import { toast } from 'sonner';
import { queryClient } from '@/lib/query/client';

/**
 * Get user connections for a user
 * Uses GET /api/v1/users/{user_id}/connections
 */
export function useUserConnections(userId: string) {
  return useQuery({
    queryKey: queryKeys.connections.all(userId),
    queryFn: () => healthService.getUserConnections(userId),
    enabled: !!userId,
  });
}

/**
 * Get workouts for a user
 * Uses GET /api/v1/users/{user_id}/workouts
 */
export function useWorkouts(userId: string, params?: WorkoutsParams) {
  return useQuery({
    queryKey: queryKeys.health.workouts(userId, params),
    queryFn: () => healthService.getWorkouts(userId, params),
    enabled: !!userId,
  });
}

/**
 * Get time series data for a user
 * Uses GET /api/v1/users/{user_id}/timeseries
 */
export function useTimeSeries(userId: string, params: TimeSeriesParams) {
  return useQuery({
    queryKey: queryKeys.health.timeseries(userId, params),
    queryFn: () => healthService.getTimeSeries(userId, params),
    enabled: !!userId && !!params.start_time && !!params.end_time,
  });
}

/**
 * Get sleep sessions for a user
 * Uses GET /api/v1/users/{user_id}/events/sleep
 */
export function useSleepSessions(userId: string, params: SleepSessionsParams) {
  return useQuery({
    queryKey: queryKeys.health.sleepSessions(userId, params),
    queryFn: () => healthService.getSleepSessions(userId, params),
    enabled: !!userId && !!params.start_date && !!params.end_date,
  });
}

/**
 * Get sleep summaries for a user
 * Uses GET /api/v1/users/{user_id}/summaries/sleep
 */
export function useSleepSummaries(userId: string, params: SummaryParams) {
  return useQuery({
    queryKey: queryKeys.health.sleepSummaries(userId, params),
    queryFn: () => healthService.getSleepSummaries(userId, params),
    enabled: !!userId && !!params.start_date && !!params.end_date,
  });
}

/**
 * Get activity summaries for a user
 * Uses GET /api/v1/users/{user_id}/summaries/activity
 */
export function useActivitySummaries(userId: string, params: SummaryParams) {
  return useQuery({
    queryKey: queryKeys.health.activitySummaries(userId, params),
    queryFn: () => healthService.getActivitySummaries(userId, params),
    enabled: !!userId && !!params.start_date && !!params.end_date,
  });
}

/**
 * Synchronize workouts/exercises/activities from fitness provider API for a specific user
 */
export function useSynchronizeDataFromProvider(
  provider: string,
  userId: string
) {
  return useMutation({
    mutationFn: () => healthService.synchronizeProvider(provider, userId),
    onSuccess: (data) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.connections.all(userId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.health.workouts(userId),
      });
      // Invalidate Garmin backfill status to refresh the UI
      if (provider === 'garmin') {
        queryClient.invalidateQueries({
          queryKey: queryKeys.garmin.backfillStatus(userId),
        });
      }
      // Show appropriate toast based on backfill status
      if (data.backfill_status?.in_progress) {
        toast.info(
          'Syncing 30 days of Garmin data. This may take a few minutes.'
        );
      } else {
        toast.success('Data synchronized successfully');
      }
    },
    onError: (error: unknown) => {
      const message =
        error instanceof Error ? error.message : 'Failed to synchronize data';
      toast.error(message);
    },
  });
}

/**
 * Get Garmin backfill status for a user
 * Polls every 15 seconds while backfill is in progress
 */
export function useGarminBackfillStatus(userId: string, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.garmin.backfillStatus(userId),
    queryFn: () => healthService.getGarminBackfillStatus(userId),
    enabled,
    refetchInterval: (query) => (query.state.data?.in_progress ? 15000 : false),
  });
}

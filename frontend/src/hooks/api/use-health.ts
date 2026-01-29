import { useMutation, useQuery } from '@tanstack/react-query';
import {
  healthService,
  type WorkoutsParams,
  type SummaryParams,
} from '@/lib/api/services/health.service';
import type {
  TimeSeriesParams,
  SleepSessionsParams,
  BodySummaryParams,
} from '@/lib/api/types';
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
 * Get body summary for a user (static, averaged, latest metrics)
 * Uses GET /api/v1/users/{user_id}/summaries/body
 */
export function useBodySummary(userId: string, params?: BodySummaryParams) {
  return useQuery({
    queryKey: queryKeys.health.bodySummary(userId, params),
    queryFn: () => healthService.getBodySummary(userId, params),
    enabled: !!userId,
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
      // Invalidate connection and workout data
      queryClient.invalidateQueries({
        queryKey: queryKeys.connections.all(userId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.health.workouts(userId),
      });

      // Auto-refresh data sections when sync completes
      queryClient.invalidateQueries({
        queryKey: queryKeys.health.activitySummaries(userId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.health.sleepSessions(userId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.health.bodySummary(userId),
      });

      // Invalidate Garmin-specific status queries
      if (provider === 'garmin') {
        queryClient.invalidateQueries({
          queryKey: queryKeys.garmin.summarySyncStatus(userId),
        });
      }

      // Show appropriate toast based on sync status
      if (
        data.sync_status?.status === 'SYNCING' ||
        data.sync_status?.status === 'WAITING'
      ) {
        toast.info(
          'Syncing Garmin data. Progress shown on your connection card.',
          { duration: 5000 }
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
 * Get Garmin summary sync status (365-day REST sync)
 * Polls every 10 seconds while sync is in progress (SYNCING or WAITING)
 */
export function useGarminSummarySyncStatus(userId: string, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.garmin.summarySyncStatus(userId),
    queryFn: () => healthService.getGarminSummarySyncStatus(userId),
    enabled,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      // Poll while SYNCING or WAITING
      return status === 'SYNCING' || status === 'WAITING' ? 10000 : false;
    },
  });
}

/**
 * Start Garmin summary sync mutation
 * Initiates 365-day REST-based data sync
 */
export function useStartGarminSummarySync(userId: string) {
  return useMutation({
    mutationFn: ({ resume = false }: { resume?: boolean } = {}) =>
      healthService.startGarminSummarySync(userId, resume),
    onSuccess: () => {
      // Invalidate status to start polling
      queryClient.invalidateQueries({
        queryKey: queryKeys.garmin.summarySyncStatus(userId),
      });
      toast.info(
        'Starting 1-year Garmin data sync. This will run in the background.'
      );
    },
    onError: (error: unknown) => {
      const message =
        error instanceof Error ? error.message : 'Failed to start sync';
      toast.error(message);
    },
  });
}

/**
 * Cancel Garmin summary sync
 * Stops the sync process; can be resumed later
 */
export function useCancelGarminSummarySync(userId: string) {
  return useMutation({
    mutationFn: () => healthService.cancelGarminSummarySync(userId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.garmin.summarySyncStatus(userId),
      });
      toast.info('Sync cancelled');
    },
    onError: (error: unknown) => {
      const message =
        error instanceof Error ? error.message : 'Failed to cancel sync';
      toast.error(message);
    },
  });
}

/**
 * Get Garmin backfill status (webhook-based, 90-day sync)
 * Polls every 10 seconds while backfill is in progress
 */
export function useGarminBackfillStatus(userId: string, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.garmin.backfillStatus(userId),
    queryFn: () => healthService.getGarminBackfillStatus(userId),
    enabled,
    refetchInterval: (query) => {
      const status = query.state.data?.overall_status;
      // Poll while in_progress
      return status === 'in_progress' ? 10000 : false;
    },
  });
}

/**
 * Retry Garmin backfill for a specific failed type
 */
export function useRetryGarminBackfill(userId: string) {
  return useMutation({
    mutationFn: (typeName: string) =>
      healthService.retryGarminBackfill(userId, typeName),
    onSuccess: (_, typeName) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.garmin.backfillStatus(userId),
      });
      toast.info(`Retrying ${typeName} sync...`);
    },
    onError: (error: unknown) => {
      const message =
        error instanceof Error ? error.message : 'Failed to retry sync';
      toast.error(message);
    },
  });
}

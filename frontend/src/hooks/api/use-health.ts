import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  healthService,
  type WorkoutsParams,
  type SummaryParams,
} from '@/lib/api/services/health.service';
import type {
  TimeSeriesParams,
  SleepSessionsParams,
  BodySummaryParams,
  HealthScoreParams,
} from '@/lib/api/types';
import { queryKeys } from '@/lib/query/keys';
import { toast } from 'sonner';
import { queryClient } from '@/lib/query/client';

/**
 * Disconnect a user from a provider
 * Uses DELETE /api/v1/users/{user_id}/connections/{provider}
 */
export function useDisconnectProvider(provider: string, userId: string) {
  return useMutation({
    mutationFn: () => healthService.disconnectProvider(userId, provider),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.connections.all(userId),
      });
      toast.success(`Disconnected from ${provider}`);
    },
    onError: (error: unknown) => {
      const message =
        error instanceof Error ? error.message : 'Failed to disconnect';
      toast.error(message);
    },
  });
}

/**
 * Get user connections for a user
 * Uses GET /api/v1/users/{user_id}/connections
 */
export function useUserConnections(userId: string, enabled: boolean = true) {
  return useQuery({
    queryKey: queryKeys.connections.all(userId),
    queryFn: () => healthService.getUserConnections(userId),
    enabled: !!userId && enabled,
    staleTime: 0,
    refetchOnWindowFocus: true,
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
 * Delete a workout event
 */
export function useDeleteWorkout(userId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (workoutId: string) =>
      healthService.deleteWorkout(userId, workoutId),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: [...queryKeys.health.all, 'workouts', userId],
      });
      qc.invalidateQueries({ queryKey: queryKeys.health.dataSummary(userId) });
      toast.success('Workout deleted');
    },
    onError: (error: unknown) => {
      const message =
        error instanceof Error ? error.message : 'Failed to delete workout';
      toast.error(message);
    },
  });
}

/**
 * Delete a sleep session event
 */
export function useDeleteSleepSession(userId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sessionId: string) =>
      healthService.deleteSleepSession(userId, sessionId),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: [...queryKeys.health.all, 'sleepSessions', userId],
      });
      qc.invalidateQueries({ queryKey: queryKeys.health.dataSummary(userId) });
      qc.invalidateQueries({
        queryKey: [...queryKeys.health.all, 'sleepSummaries', userId],
      });
      qc.invalidateQueries({
        queryKey: [...queryKeys.health.all, 'healthScores', userId],
      });
      toast.success('Sleep session deleted');
    },
    onError: (error: unknown) => {
      const message =
        error instanceof Error
          ? error.message
          : 'Failed to delete sleep session';
      toast.error(message);
    },
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
 * Get per-user data summary with counts by type and provider
 * Uses GET /api/v1/users/{user_id}/summaries/data
 */
export function useUserDataSummary(userId: string) {
  return useQuery({
    queryKey: queryKeys.health.dataSummary(userId),
    queryFn: () => healthService.getUserDataSummary(userId),
    enabled: !!userId,
    staleTime: 2 * 60 * 1000,
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
 * Get health scores (sleep, recovery, readiness, etc.) for a user
 * Uses GET /api/v1/users/{user_id}/health-scores
 */
export function useHealthScores(userId: string, params: HealthScoreParams) {
  return useQuery({
    queryKey: queryKeys.health.healthScores(userId, params),
    queryFn: () => healthService.getHealthScores(userId, params),
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
    onSuccess: () => {
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
      queryClient.invalidateQueries({
        queryKey: queryKeys.health.dataSummary(userId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.health.healthScores(userId),
      });

      toast.success('Data synchronized successfully');
    },
    onError: (error: unknown) => {
      const message =
        error instanceof Error ? error.message : 'Failed to synchronize data';
      toast.error(message);
    },
  });
}

/**
 * Trigger historical data sync for a provider
 * Garmin: 30-day webhook backfill; others: pull API with date range
 */
export function useSyncHistoricalData(provider: string, userId: string) {
  return useMutation({
    mutationFn: (days?: number) =>
      healthService.syncHistoricalData(provider, userId, days),
    onSuccess: (data) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.connections.all(userId),
      });
      if (data.method === 'webhook_backfill') {
        queryClient.invalidateQueries({
          queryKey: queryKeys.garmin.backfillStatus(userId),
        });
        toast.success('Historical backfill started');
      } else {
        toast.success('Historical sync queued');
      }
    },
    onError: (error: unknown) => {
      const message =
        error instanceof Error
          ? error.message
          : 'Failed to start historical sync';
      toast.error(message);
    },
  });
}

/**
 * Get Garmin backfill status (webhook-based, 30-day sync)
 * Polls every 10 seconds while backfill is in progress
 */
export function useGarminBackfillStatus(userId: string, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.garmin.backfillStatus(userId),
    queryFn: () => healthService.getGarminBackfillStatus(userId),
    enabled,
    refetchInterval: (query) => {
      const status = query.state.data?.overall_status;
      // Poll while in_progress OR retry_in_progress
      return status === 'in_progress' || status === 'retry_in_progress'
        ? 10000
        : false;
    },
  });
}

/**
 * Cancel an in-progress Garmin backfill
 * Sets cancellation flag; backfill stops after current type completes
 */
export function useGarminCancelBackfill(userId: string) {
  return useMutation({
    mutationFn: () => healthService.cancelGarminBackfill(userId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.garmin.backfillStatus(userId),
      });
      toast.info('Backfill cancellation requested');
    },
    onError: (error: unknown) => {
      const message =
        error instanceof Error ? error.message : 'Failed to cancel backfill';
      toast.error(message);
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

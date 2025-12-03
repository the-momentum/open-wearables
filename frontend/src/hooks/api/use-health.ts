import { useQuery } from '@tanstack/react-query';
import {
  healthService,
  type WorkoutsParams,
} from '@/lib/api/services/health.service';
import { queryKeys } from '@/lib/query/keys';

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
 * Get heart rate data for a user
 * Uses GET /api/v1/users/{user_id}/heart-rate
 */
export function useHeartRate(userId: string) {
  return useQuery({
    queryKey: queryKeys.health.heartRate(userId),
    queryFn: () => healthService.getHeartRate(userId),
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

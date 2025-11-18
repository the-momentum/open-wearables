import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { healthService } from '@/lib/api/services/health.service';
import { queryKeys } from '@/lib/query/keys';
import { toast } from 'sonner';
import { getErrorMessage } from '@/lib/errors/handler';

// Get available providers
export function useProviders() {
  return useQuery({
    queryKey: queryKeys.health.providers(),
    queryFn: () => healthService.getProviders(),
  });
}

// Get user connections
export function useUserConnections(userId: string) {
  return useQuery({
    queryKey: queryKeys.health.connections(userId),
    queryFn: () => healthService.getUserConnections(userId),
    enabled: !!userId,
  });
}

// Get heart rate data
export function useHeartRateData(userId: string, days: number = 7) {
  return useQuery({
    queryKey: queryKeys.health.heartRate(userId, days),
    queryFn: () => healthService.getHeartRateData(userId, days),
    enabled: !!userId,
  });
}

// Get sleep data
export function useSleepData(userId: string, days: number = 7) {
  return useQuery({
    queryKey: queryKeys.health.sleep(userId, days),
    queryFn: () => healthService.getSleepData(userId, days),
    enabled: !!userId,
  });
}

// Get activity data
export function useActivityData(userId: string, days: number = 7) {
  return useQuery({
    queryKey: queryKeys.health.activity(userId, days),
    queryFn: () => healthService.getActivityData(userId, days),
    enabled: !!userId,
  });
}

// Get health summary
export function useHealthSummary(userId: string, period: string = '7d') {
  return useQuery({
    queryKey: queryKeys.health.summary(userId, period),
    queryFn: () => healthService.getHealthSummary(userId, period),
    enabled: !!userId,
  });
}

// Generate connection link
export function useGenerateConnectionLink() {
  return useMutation({
    mutationFn: ({
      userId,
      providerId,
    }: {
      userId: string;
      providerId: string;
    }) => healthService.generateConnectionLink(userId, providerId),
    onSuccess: () => {
      toast.success('Connection link generated successfully');
    },
    onError: (error) => {
      toast.error(
        `Failed to generate connection link: ${getErrorMessage(error)}`
      );
    },
  });
}

// Disconnect provider
export function useDisconnectProvider() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      userId,
      connectionId,
    }: {
      userId: string;
      connectionId: string;
    }) => healthService.disconnectProvider(userId, connectionId),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.health.connections(variables.userId),
      });
      toast.success('Provider disconnected successfully');
    },
    onError: (error) => {
      toast.error(`Failed to disconnect provider: ${getErrorMessage(error)}`);
    },
  });
}

// Sync user data
export function useSyncUserData() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (userId: string) => healthService.syncUserData(userId),
    onSuccess: (_, userId) => {
      // Invalidate all health-related queries for this user
      queryClient.invalidateQueries({
        queryKey: queryKeys.health.connections(userId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.health.summary(userId),
      });
      // Invalidate specific health data types
      queryClient.invalidateQueries({
        predicate: (query) => {
          const key = query.queryKey;
          return (
            Array.isArray(key) && key[0] === 'health' && key.includes(userId)
          );
        },
      });
      toast.success('Data sync initiated');
    },
    onError: (error) => {
      toast.error(`Failed to sync data: ${getErrorMessage(error)}`);
    },
  });
}

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  priorityService,
  type ProviderPriorityBulkUpdate,
} from '@/lib/api/services/priority.service';
import { queryKeys } from '@/lib/query/keys';
import { toast } from 'sonner';
import { getErrorMessage } from '@/lib/errors/handler';

// ==================== Provider Priorities ====================

export function useProviderPriorities() {
  return useQuery({
    queryKey: queryKeys.priorities.providers(),
    queryFn: () => priorityService.getProviderPriorities(),
  });
}

export function useBulkUpdateProviderPriorities() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ProviderPriorityBulkUpdate) =>
      priorityService.bulkUpdateProviderPriorities(data),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.priorities.all,
      });
      toast.success('Provider priorities updated successfully');
    },
    onError: (error) => {
      toast.error(`Failed to update priorities: ${getErrorMessage(error)}`);
    },
  });
}

// ==================== User Data Sources ====================

export function useUserDataSources(userId: string) {
  return useQuery({
    queryKey: queryKeys.priorities.dataSources(userId),
    queryFn: () => priorityService.getUserDataSources(userId),
    enabled: !!userId,
  });
}

export function useUpdateDataSourceEnabled() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      userId,
      dataSourceId,
      isEnabled,
    }: {
      userId: string;
      dataSourceId: string;
      isEnabled: boolean;
    }) =>
      priorityService.updateDataSourceEnabled(userId, dataSourceId, {
        is_enabled: isEnabled,
      }),
    onSuccess: async (_, variables) => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.priorities.dataSources(variables.userId),
      });
      toast.success(
        variables.isEnabled ? 'Data source enabled' : 'Data source disabled'
      );
    },
    onError: (error) => {
      toast.error(`Failed to update data source: ${getErrorMessage(error)}`);
    },
  });
}

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  archivalService,
  type ArchivalSettingsUpdate,
} from '@/lib/api/services/archival.service';
import { queryKeys } from '@/lib/query/keys';
import { toast } from 'sonner';
import { getErrorMessage } from '@/lib/errors/handler';

export function useArchivalSettings() {
  return useQuery({
    queryKey: queryKeys.archival.settings(),
    queryFn: () => archivalService.getSettings(),
    staleTime: 30_000, // Cache for 30s — storage sizes don't change rapidly
  });
}

export function useUpdateArchivalSettings() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ArchivalSettingsUpdate) =>
      archivalService.updateSettings(data),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.archival.all,
      });
      toast.success('Data lifecycle settings updated');
    },
    onError: (error) => {
      toast.error(`Failed to update settings: ${getErrorMessage(error)}`);
    },
  });
}

export function useTriggerArchival() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => archivalService.triggerArchival(),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.archival.all,
      });
      toast.success(
        `Archival job dispatched (task ${result.task_id.slice(0, 8)}…). Results will appear on the next page refresh.`
      );
    },
    onError: (error) => {
      toast.error(`Archival failed: ${getErrorMessage(error)}`);
    },
  });
}

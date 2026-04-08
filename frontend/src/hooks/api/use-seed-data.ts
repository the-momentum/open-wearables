import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  seedDataService,
  type SeedDataRequest,
} from '@/lib/api/services/seed-data.service';
import { queryKeys } from '@/lib/query/keys';
import { toast } from 'sonner';
import { getErrorMessage } from '@/lib/errors/handler';

export function useSeedPresets() {
  return useQuery({
    queryKey: queryKeys.seedData.presets(),
    queryFn: () => seedDataService.getPresets(),
    staleTime: Infinity, // Presets are static
  });
}

export function useGenerateSeedData() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: SeedDataRequest) => seedDataService.generate(data),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.dashboard.all,
      });
      await queryClient.invalidateQueries({
        queryKey: queryKeys.users.all,
      });
      toast.success(
        `Seed data generation started (task ${result.task_id.slice(0, 8)}...). New users will appear after the task completes.`
      );
    },
    onError: (error) => {
      toast.error(`Seed data generation failed: ${getErrorMessage(error)}`);
    },
  });
}

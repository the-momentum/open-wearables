import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { developersService } from '@/lib/api/services/developers.service';
import { queryKeys } from '@/lib/query/keys';
import { toast } from 'sonner';
import { getErrorMessage } from '@/lib/errors/handler';

export function useDevelopers() {
  return useQuery({
    queryKey: queryKeys.developers.list(),
    queryFn: () => developersService.getDevelopers(),
  });
}

export function useDeleteDeveloper() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => developersService.deleteDeveloper(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.developers.list() });
      toast.success('Team member removed successfully');
    },
    onError: (error) => {
      toast.error(`Failed to remove team member: ${getErrorMessage(error)}`);
    },
  });
}


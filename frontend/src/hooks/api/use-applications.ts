import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { applicationsService } from '@/lib/api/services/applications.service';
import type { ApplicationCreate } from '@/lib/api/types';
import { queryKeys } from '@/lib/query/keys';
import { toast } from 'sonner';
import { getErrorMessage } from '@/lib/errors/handler';

export function useApplications() {
  return useQuery({
    queryKey: queryKeys.applications.list(),
    queryFn: () => applicationsService.list(),
  });
}

export function useCreateApplication() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ApplicationCreate) => applicationsService.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.applications.list(),
      });
      toast.success('Application created successfully');
    },
    onError: (error) => {
      toast.error(`Failed to create application: ${getErrorMessage(error)}`);
    },
  });
}

export function useDeleteApplication() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (appId: string) => applicationsService.delete(appId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.applications.list(),
      });
      toast.success('Application deleted successfully');
    },
    onError: (error) => {
      toast.error(`Failed to delete application: ${getErrorMessage(error)}`);
    },
  });
}

export function useRotateApplicationSecret() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (appId: string) => applicationsService.rotateSecret(appId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.applications.list(),
      });
      toast.success('Application secret rotated successfully');
    },
    onError: (error) => {
      toast.error(
        `Failed to rotate application secret: ${getErrorMessage(error)}`
      );
    },
  });
}

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { credentialsService } from '@/lib/api/services/credentials.service';
import type { ApiKeyCreate, ApiKeyUpdate } from '@/lib/api/types';
import { queryKeys } from '@/lib/query/keys';
import { toast } from 'sonner';
import { getErrorMessage } from '@/lib/errors/handler';

// Get all API keys
export function useApiKeys() {
  return useQuery({
    queryKey: queryKeys.credentials.list(),
    queryFn: () => credentialsService.getApiKeys(),
  });
}

// Get single API key
export function useApiKey(id: string) {
  return useQuery({
    queryKey: queryKeys.credentials.detail(id),
    queryFn: () => credentialsService.getApiKey(id),
    enabled: !!id,
  });
}

// Create API key
export function useCreateApiKey() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ApiKeyCreate) => credentialsService.createApiKey(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.credentials.list() });
      toast.success('API key created successfully');
    },
    onError: (error) => {
      toast.error(`Failed to create API key: ${getErrorMessage(error)}`);
    },
  });
}

// Update API key
export function useUpdateApiKey() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ApiKeyUpdate }) =>
      credentialsService.updateApiKey(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.credentials.list() });
      toast.success('API key updated successfully');
    },
    onError: (error) => {
      toast.error(`Failed to update API key: ${getErrorMessage(error)}`);
    },
  });
}

// Delete API key
export function useDeleteApiKey() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => credentialsService.deleteApiKey(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.credentials.list() });
      toast.success('API key deleted successfully');
    },
    onError: (error) => {
      toast.error(`Failed to delete API key: ${getErrorMessage(error)}`);
    },
  });
}

// Rotate API key
export function useRotateApiKey() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => credentialsService.rotateApiKey(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.credentials.list() });
      toast.success('API key rotated successfully');
    },
    onError: (error) => {
      toast.error(`Failed to rotate API key: ${getErrorMessage(error)}`);
    },
  });
}

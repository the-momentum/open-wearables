import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { webhooksService } from '@/lib/api';
import { getErrorMessage } from '@/lib/errors/handler';
import { queryKeys } from '@/lib/query/keys';
import type {
  WebhookEndpointCreate,
  WebhookEndpointUpdate,
} from '@/lib/api/types';

export function useWebhookEventTypes() {
  return useQuery({
    queryKey: queryKeys.webhooks.eventTypes(),
    queryFn: () => webhooksService.listEventTypes(),
    staleTime: Infinity,
    gcTime: Infinity,
  });
}

export function useWebhookEndpoints() {
  return useQuery({
    queryKey: queryKeys.webhooks.list(),
    queryFn: () => webhooksService.list(),
    retry: false,
  });
}

export function useWebhookEndpoint(id: string) {
  return useQuery({
    queryKey: queryKeys.webhooks.detail(id),
    queryFn: () => webhooksService.getById(id),
    enabled: !!id,
  });
}

export function useCreateWebhookEndpoint() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: WebhookEndpointCreate) => webhooksService.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.webhooks.lists() });
      toast.success('Webhook created');
    },
    onError: (error) => {
      toast.error(getErrorMessage(error));
    },
  });
}

export function useUpdateWebhookEndpoint() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: WebhookEndpointUpdate }) =>
      webhooksService.update(id, data),
    onSuccess: (updated, { id }) => {
      queryClient.setQueryData(queryKeys.webhooks.detail(id), updated);
      queryClient.invalidateQueries({ queryKey: queryKeys.webhooks.lists() });
      toast.success('Webhook updated');
    },
    onError: (error) => {
      toast.error(getErrorMessage(error));
    },
  });
}

export function useDeleteWebhookEndpoint() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => webhooksService.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.webhooks.lists() });
      toast.success('Webhook deleted');
    },
    onError: (error) => {
      toast.error(getErrorMessage(error));
    },
  });
}

export function useWebhookSecret(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.webhooks.secret(id),
    queryFn: () => webhooksService.getSecret(id),
    enabled: !!id && (options?.enabled ?? false),
    staleTime: Infinity,
  });
}

export function useSendTestWebhook() {
  return useMutation({
    mutationFn: ({ id, eventType }: { id: string; eventType?: string }) =>
      webhooksService.sendTest(id, eventType),
    onSuccess: (data) => {
      toast.success(`Test event sent (id: ${data.message_id})`);
    },
    onError: (error) => {
      toast.error(getErrorMessage(error));
    },
  });
}

export function useWebhookMessages(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.webhooks.messages(),
    queryFn: () => webhooksService.listMessages(),
    enabled: options?.enabled ?? true,
    retry: false,
  });
}

export function useWebhookAttempts(id: string) {
  return useQuery({
    queryKey: queryKeys.webhooks.attempts(id),
    queryFn: () => webhooksService.listAttempts(id),
    enabled: !!id,
  });
}

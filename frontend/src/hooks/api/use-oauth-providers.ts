import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { oauthService } from '@/lib/api/services/oauth.service';
import type { OAuthProvidersUpdate } from '@/lib/api/services/oauth.service';
import { queryKeys } from '@/lib/query/keys';
import { toast } from 'sonner';
import { getErrorMessage } from '@/lib/errors/handler';

// Get OAuth providers
export function useOAuthProviders(
  cloudOnly: boolean = false,
  enabledOnly: boolean = false
) {
  return useQuery({
    queryKey: queryKeys.oauthProviders.list(cloudOnly, enabledOnly),
    queryFn: () => oauthService.getProviders(cloudOnly, enabledOnly),
  });
}

// Update OAuth providers (bulk is_enabled)
export function useUpdateOAuthProviders() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: OAuthProvidersUpdate) =>
      oauthService.updateProviders(data),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.oauthProviders.all,
      });
      toast.success('Provider settings updated successfully');
    },
    onError: (error) => {
      toast.error(`Failed to update providers: ${getErrorMessage(error)}`);
    },
  });
}

// Update live_sync_mode for a single provider (immediate, no save button)
export function useUpdateProviderLiveSyncMode(provider: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (live_sync_mode: 'pull' | 'webhook') =>
      oauthService.updateProviderSetting(provider, { live_sync_mode }),
    onMutate: async (live_sync_mode) => {
      await queryClient.cancelQueries({
        queryKey: queryKeys.oauthProviders.all,
      });
      const previousData = queryClient.getQueriesData<
        import('@/lib/api/types').Provider[]
      >({
        queryKey: queryKeys.oauthProviders.all,
      });
      queryClient.setQueriesData<import('@/lib/api/types').Provider[]>(
        { queryKey: queryKeys.oauthProviders.all },
        (old) =>
          old?.map((p) =>
            p.provider === provider ? { ...p, live_sync_mode } : p
          ) ?? old
      );
      return { previousData };
    },
    onError: (error, _vars, context) => {
      if (context?.previousData) {
        for (const [queryKey, data] of context.previousData) {
          queryClient.setQueryData(queryKey, data);
        }
      }
      toast.error(`Failed to update sync mode: ${getErrorMessage(error)}`);
    },
    onSuccess: () => {
      toast.success('Sync mode updated');
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.oauthProviders.all });
    },
  });
}

import { useState, useEffect, useMemo } from 'react';
import {
  useOAuthProviders,
  useUpdateOAuthProviders,
} from '@/hooks/api/use-oauth-providers';
import { Loader2, CheckCircle2 } from 'lucide-react';
import { ProviderItem } from '@/components/settings/providers/provider-item';

export function ProvidersTab() {
  const {
    data: providers,
    isLoading,
    error,
    refetch,
  } = useOAuthProviders(true);
  const updateMutation = useUpdateOAuthProviders();

  const [localToggleStates, setLocalToggleStates] = useState<
    Record<string, boolean>
  >({});
  const [hasInitialized, setHasInitialized] = useState(false);

  useEffect(() => {
    if (providers && providers.length > 0 && !hasInitialized) {
      const initial: Record<string, boolean> = {};
      providers.forEach((provider) => {
        initial[provider.provider] = provider.is_enabled;
      });
      setLocalToggleStates(initial);
      setHasInitialized(true);
    }
  }, [providers, hasInitialized]);

  const hasChanges = useMemo(() => {
    if (!providers) return false;

    return providers.some(
      (provider) => localToggleStates[provider.provider] !== provider.is_enabled
    );
  }, [providers, localToggleStates]);

  const handleToggleProvider = (providerId: string) => {
    setLocalToggleStates((prev) => ({
      ...prev,
      [providerId]: !prev[providerId],
    }));
  };

  const handleSave = async () => {
    if (!providers) return;
    await updateMutation.mutateAsync({ providers: localToggleStates });
  };

  if (isLoading) {
    return (
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-12">
        <div className="flex items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-zinc-400" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-12 text-center">
        <p className="text-zinc-400 mb-4">Failed to load OAuth providers</p>
        <button
          onClick={() => refetch()}
          className="px-4 py-2 bg-white text-black rounded-md text-sm font-medium hover:bg-zinc-200 transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!providers || providers.length === 0) {
    return (
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-12 text-center">
        <p className="text-zinc-400">No OAuth providers available</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-medium text-white">OAuth Providers</h2>
          <p className="text-sm text-zinc-500 mt-1">
            Configure which OAuth providers are available to your end users
          </p>
        </div>
        {hasChanges && (
          <button
            onClick={handleSave}
            disabled={updateMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-white text-black rounded-md text-sm font-medium hover:bg-zinc-200 transition-colors disabled:opacity-50"
          >
            {updateMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <CheckCircle2 className="h-4 w-4" />
                Save Changes
              </>
            )}
          </button>
        )}
      </div>

      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-zinc-800">
          <h3 className="text-sm font-medium text-white">
            Available Providers
          </h3>
          <p className="text-xs text-zinc-500 mt-1">
            Enable or disable OAuth providers for your application
          </p>
        </div>

        <div className="divide-y divide-zinc-800/50">
          {providers.map((provider) => (
            <ProviderItem
              key={provider.provider}
              provider={provider}
              localToggleState={
                localToggleStates[provider.provider] ?? provider.is_enabled
              }
              onToggle={() => handleToggleProvider(provider.provider)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

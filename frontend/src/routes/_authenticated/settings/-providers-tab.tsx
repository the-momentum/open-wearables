import { useState, useEffect, useMemo } from 'react';
import {
  useOAuthProviders,
  useUpdateOAuthProviders,
} from '@/hooks/api/use-oauth-providers';
import { Loader2, CheckCircle2 } from 'lucide-react';
import { ProviderItem } from '@/components/settings/providers/provider-item';
import { Button } from '@/components/ui/button';

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
    if (!providers || !hasInitialized) return false;

    return providers.some(
      (provider) => localToggleStates[provider.provider] !== provider.is_enabled
    );
  }, [providers, localToggleStates, hasInitialized]);

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
      <div className="rounded-2xl border border-border/60 bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-xl p-12">
        <div className="flex items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-border/60 bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-xl p-12 text-center">
        <p className="text-muted-foreground mb-4">
          Failed to load OAuth providers
        </p>
        <Button variant="outline" onClick={() => refetch()}>
          Retry
        </Button>
      </div>
    );
  }

  if (!providers || providers.length === 0) {
    return (
      <div className="rounded-2xl border border-border/60 bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-xl p-12 text-center">
        <p className="text-muted-foreground">No OAuth providers available</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-medium text-foreground">OAuth Providers</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Configure which OAuth providers are available to your end users
        </p>
      </div>

      <div className="rounded-2xl border border-border/60 bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-border/60">
          <h3 className="text-sm font-medium text-foreground">
            Available Providers
          </h3>
          <p className="text-xs text-muted-foreground mt-1">
            Enable or disable OAuth providers for your application
          </p>
        </div>

        <div className="divide-y divide-border/40">
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

      {hasChanges && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-4 rounded-lg border border-border bg-card px-6 py-3 shadow-lg shadow-black/50">
          <p className="text-sm text-foreground/90">You have unsaved changes</p>
          <Button onClick={handleSave} disabled={updateMutation.isPending}>
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
          </Button>
        </div>
      )}
    </div>
  );
}

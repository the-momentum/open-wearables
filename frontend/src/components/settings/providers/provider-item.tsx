import { Provider } from '@/lib/api/types';
import { API_CONFIG } from '@/lib/api/config';
import { Switch } from '@/components/ui/switch';
import { useState } from 'react';
import { cn } from '@/lib/utils';
import { useUpdateProviderLiveSyncMode } from '@/hooks/api/use-oauth-providers';
import { Timer, Zap } from 'lucide-react';

interface ProviderItemProps {
  provider: Provider;
  localToggleState: boolean;
  onToggle: () => void;
}

export function ProviderItem({
  provider,
  localToggleState,
  onToggle,
}: ProviderItemProps) {
  const [imageError, setImageError] = useState(false);
  const isEnabledInBackend = provider.is_enabled;
  const iconUrl = provider.icon_url
    ? new URL(provider.icon_url, API_CONFIG.baseUrl).toString()
    : null;

  const { mutate: updateLiveSyncMode, isPending } =
    useUpdateProviderLiveSyncMode(provider.provider);

  const currentMode = provider.live_sync_mode ?? 'pull';

  return (
    <div className="px-6 py-4 hover:bg-muted/40 transition-colors">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4 flex-1">
          <div className="flex-shrink-0 p-2 rounded-lg overflow-hidden bg-white">
            {iconUrl && !imageError ? (
              <img
                src={iconUrl}
                alt={provider.name}
                className="h-12 w-12 object-contain"
                onError={() => {
                  setImageError(true);
                }}
              />
            ) : (
              <div className="h-12 w-12 bg-white text-muted-foreground font-medium rounded-lg flex items-center justify-center">
                {provider.name.charAt(0).toUpperCase()}
              </div>
            )}
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h4 className="text-sm font-medium text-foreground">
                {provider.name}
              </h4>
              {isEnabledInBackend ? (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-500/20 text-green-400">
                  Enabled
                </span>
              ) : (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-muted text-muted-foreground">
                  Disabled
                </span>
              )}
            </div>

            <div className="mt-2">
              {provider.live_sync_configurable ? (
                /* Segmented control for configurable providers */
                <div className="inline-flex items-center gap-1 p-1 rounded-lg bg-card border border-border/60">
                  {(
                    [
                      { mode: 'pull', label: 'Periodic pull', Icon: Timer },
                      { mode: 'webhook', label: 'Webhook', Icon: Zap },
                    ] as const
                  ).map(({ mode, label, Icon }) => (
                    <button
                      key={mode}
                      type="button"
                      disabled={isPending}
                      onClick={() => updateLiveSyncMode(mode)}
                      className={cn(
                        'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all duration-150',
                        currentMode === mode && mode === 'webhook'
                          ? 'bg-indigo-500/20 text-indigo-300 shadow-sm border border-indigo-500/30'
                          : currentMode === mode && mode === 'pull'
                            ? 'bg-muted-foreground/40 text-foreground shadow-sm border border-zinc-600'
                            : 'text-muted-foreground hover:text-foreground/90 hover:bg-muted/60'
                      )}
                    >
                      <Icon className="h-3 w-3" />
                      {label}
                    </button>
                  ))}
                </div>
              ) : (
                /* Static badge for non-configurable providers */
                <div className="inline-flex items-center gap-1.5">
                  {currentMode === 'webhook' ? (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                      <Zap className="h-3 w-3" />
                      Webhook only
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-muted text-muted-foreground border border-border">
                      <Timer className="h-3 w-3" />
                      Periodic pull only
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="flex-shrink-0 ml-4">
          <Switch
            checked={localToggleState}
            onCheckedChange={onToggle}
            aria-label={`Toggle ${provider.name} provider`}
          />
        </div>
      </div>
    </div>
  );
}

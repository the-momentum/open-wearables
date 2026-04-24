import { Provider } from '@/lib/api/types';
import { API_CONFIG } from '@/lib/api/config';
import { Switch } from '@/components/ui/switch';
import { useState } from 'react';
import { cn } from '@/lib/utils';
import { useUpdateProviderLiveSyncMode } from '@/hooks/api/use-oauth-providers';

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

  const { mutate: updateLiveSyncMode } = useUpdateProviderLiveSyncMode(
    provider.provider
  );

  return (
    <div className="px-6 py-4 hover:bg-zinc-800/30 transition-colors">
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
              <div className="h-12 w-12 bg-white text-zinc-500 font-medium rounded-lg flex items-center justify-center">
                {provider.name.charAt(0).toUpperCase()}
              </div>
            )}
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h4 className="text-sm font-medium text-white">
                {provider.name}
              </h4>
              {isEnabledInBackend ? (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-500/20 text-green-400">
                  Enabled
                </span>
              ) : (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-zinc-800 text-zinc-400">
                  Disabled
                </span>
              )}
            </div>

            {provider.live_sync_configurable && (
              <div className="flex items-center gap-2 mt-2">
                <span className="text-xs text-zinc-500">Live sync</span>
                <div
                  role="group"
                  aria-label="Live sync mode"
                  className="flex items-center rounded-md bg-zinc-800 p-0.5"
                >
                  {(['pull', 'webhook'] as const).map((mode) => (
                    <button
                      key={mode}
                      type="button"
                      aria-pressed={
                        (provider.live_sync_mode ?? 'pull') === mode
                      }
                      onClick={() => updateLiveSyncMode(mode)}
                      className={cn(
                        'px-2 py-0.5 text-xs rounded transition-colors',
                        (provider.live_sync_mode ?? 'pull') === mode
                          ? 'bg-zinc-600 text-white'
                          : 'text-zinc-400 hover:text-zinc-300'
                      )}
                    >
                      {mode === 'pull' ? 'Periodic pull' : 'Webhook'}
                    </button>
                  ))}
                </div>
              </div>
            )}
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

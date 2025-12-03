import { Provider } from '@/lib/api/types';
import { Switch } from '@/components/ui/switch';

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
  const isEnabledInBackend = provider.is_enabled;
  const iconUrl = provider.icon_url
    ? new URL(provider.icon_url, import.meta.env.VITE_API_URL).toString()
    : null;
  return (
    <div className="px-6 py-4 hover:bg-zinc-800/30 transition-colors">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4 flex-1">
          <div
            className="flex-shrink-0 p-2 rounded-lg overflow-hidden bg-white"
            data-has-icon={!!provider.icon_url}
          >
            {iconUrl ? (
              <img
                src={iconUrl}
                alt={provider.name}
                className="h-12 w-12 object-contain"
                onError={(e) => {
                  (e.target as HTMLImageElement).style.display = 'none';
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
          </div>
        </div>

        <div className="flex-shrink-0 ml-4">
          <Switch checked={localToggleState} onCheckedChange={onToggle} />
        </div>
      </div>
    </div>
  );
}

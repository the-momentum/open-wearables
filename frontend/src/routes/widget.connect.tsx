import { createFileRoute } from '@tanstack/react-router';
import { useState, useMemo } from 'react';
import { Check, ChevronRight, Loader2, Lock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useOAuthProviders } from '@/hooks/api/use-oauth-providers';
import { API_CONFIG } from '@/lib/api/config';

export const Route = createFileRoute('/widget/connect')({
  component: ConnectWidgetPage,
});

type ConnectionState = 'idle' | 'connecting' | 'success' | 'error';

function ConnectWidgetPage() {
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);
  const [connectionState, setConnectionState] =
    useState<ConnectionState>('idle');
  const [errorMessage, setErrorMessage] = useState<string>('');

  const { data: apiProviders, isLoading } = useOAuthProviders(true, true);

  const displayProviders = useMemo(() => {
    if (!apiProviders) return [];
    return apiProviders.map((apiProvider) => {
      return {
        id: apiProvider.provider,
        name: apiProvider.name,
        description: 'Connect your device',
        logoPath: apiProvider.icon_url
          ? `${API_CONFIG.baseUrl}${apiProvider.icon_url}`
          : '',
        isAvailable: apiProvider.is_enabled,
      };
    });
  }, [apiProviders]);

  const handleConnect = async (providerId: string, providerName: string) => {
    const provider = displayProviders.find((p) => p.id === providerId);
    if (!provider?.isAvailable) {
      return;
    }

    setSelectedProvider(providerId);
    setConnectionState('connecting');
    setErrorMessage('');

    try {
      // In production, this would redirect to OAuth provider
      // For now, simulate the OAuth flow
      await simulateOAuthFlow();

      setConnectionState('success');

      // Notify parent window
      if (window.parent !== window) {
        window.parent.postMessage(
          {
            type: 'wearable_connected',
            provider: providerId,
            providerName: providerName,
          },
          '*'
        );
      }

      // Auto-close after success
      setTimeout(() => {
        if (window.parent !== window) {
          window.parent.postMessage({ type: 'wearable_widget_close' }, '*');
        }
      }, 2000);
    } catch (err) {
      setConnectionState('error');
      setErrorMessage(err instanceof Error ? err.message : 'Connection failed');
    }
  };

  // Simulate OAuth flow (in production this would redirect to provider's OAuth page)
  const simulateOAuthFlow = (): Promise<void> => {
    return new Promise((resolve, reject) => {
      setTimeout(() => {
        // 90% success rate for simulation
        if (Math.random() > 0.1) {
          resolve();
        } else {
          reject(new Error('OAuth authorization was cancelled or failed'));
        }
      }, 2000);
    });
  };

  if (connectionState === 'success') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-zinc-950 p-6">
        <div className="w-full max-w-md rounded-2xl bg-zinc-900/40 border border-white/5 p-10 text-center">
          <div className="flex justify-center mb-6">
            <div className="rounded-full bg-green-500/20 p-4">
              <Check className="h-10 w-10 text-green-400" />
            </div>
          </div>
          <h2 className="text-2xl font-medium text-white mb-3">
            Successfully Connected!
          </h2>
          <p className="text-zinc-400">
            Your device has been connected and will start syncing data shortly.
          </p>
        </div>
      </div>
    );
  }

  if (connectionState === 'error') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-zinc-950 p-6">
        <div className="w-full max-w-md rounded-2xl bg-zinc-900/40 border border-white/5 p-10 text-center">
          <h2 className="text-2xl font-medium text-red-400 mb-3">
            Connection Failed
          </h2>
          <p className="text-zinc-400 mb-8">{errorMessage}</p>
          <Button
            className="w-full bg-zinc-800 hover:bg-zinc-700 text-white border-0"
            onClick={() => {
              setConnectionState('idle');
              setSelectedProvider(null);
            }}
          >
            Try Again
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6 relative overflow-hidden bg-zinc-950 text-zinc-200 selection:bg-white/20">
      {/* Ambient Background Effect */}
      <div
        className="absolute top-0 left-0 w-full h-full bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(120,119,198,0.1),rgba(255,255,255,0))] pointer-events-none"
        aria-hidden="true"
      />

      {/* Header */}
      <div className="relative z-10 text-center mb-14 space-y-3">
        <h1 className="text-4xl font-medium text-white tracking-tight">
          Connect a device
        </h1>
        <p className="text-lg text-zinc-400">Select your wearable platform</p>
      </div>

      {/* Grid Layout */}
      <div className="relative z-10 grid grid-cols-1 md:grid-cols-2 gap-6 w-full max-w-4xl">
        {isLoading ? (
          <div className="col-span-2 flex justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-zinc-500" />
          </div>
        ) : (
          displayProviders.map((provider) => {
            const isConnecting =
              selectedProvider === provider.id &&
              connectionState === 'connecting';

            return (
              <button
                key={provider.id}
                onClick={() => handleConnect(provider.id, provider.name)}
                disabled={!provider.isAvailable || isConnecting}
                className={`group relative flex flex-col items-center text-center p-10 rounded-2xl bg-zinc-900/40 border border-white/5 hover:bg-zinc-900/80 hover:border-white/10 transition-all duration-300 ease-out outline-none focus:ring-2 focus:ring-white/20 ${
                  !provider.isAvailable ? 'opacity-50 cursor-not-allowed' : ''
                } ${isConnecting ? 'border-white/20' : ''}`}
              >
                <div className="mb-8 flex items-center justify-center h-20 w-20 bg-white rounded-2xl shadow-lg shadow-black/20 group-hover:scale-105 transition-transform duration-300">
                  <img
                    src={provider.logoPath}
                    alt={`${provider.name} logo`}
                    className="w-14 h-14 object-contain"
                  />
                </div>

                <h3 className="text-xl font-medium text-white mb-3">
                  {provider.name}
                </h3>
                <p className="text-base text-zinc-500 max-w-xs leading-relaxed">
                  {provider.description}
                </p>

                <div className="mt-8 flex items-center gap-1.5 text-base font-medium text-zinc-200 group-hover:text-white transition-colors">
                  {isConnecting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Connecting...
                    </>
                  ) : !provider.isAvailable ? (
                    'Coming Soon'
                  ) : (
                    <>
                      Connect
                      <ChevronRight className="w-4 h-4 stroke-[1.5]" />
                    </>
                  )}
                </div>
              </button>
            );
          })
        )}
      </div>

      {/* Footer Security */}
      <div className="mt-20 flex items-center gap-2 text-zinc-500 text-base font-normal opacity-80 hover:opacity-100 transition-opacity">
        <Lock className="w-4 h-4 stroke-[1.5]" />
        <span>Your data is encrypted and secure</span>
      </div>
    </div>
  );
}

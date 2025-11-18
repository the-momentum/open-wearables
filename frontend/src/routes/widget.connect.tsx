import { createFileRoute } from '@tanstack/react-router';
import { useState } from 'react';
import { Check, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useProviders } from '@/hooks/api/use-health';
import { LoadingState } from '@/components/common/loading-spinner';
import { ErrorState } from '@/components/common/error-state';
import type { Provider } from '@/lib/api/types';

export const Route = createFileRoute('/widget/connect')({
  component: ConnectWidgetPage,
});

type ConnectionState = 'idle' | 'connecting' | 'success' | 'error';

function ConnectWidgetPage() {
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);
  const [connectionState, setConnectionState] =
    useState<ConnectionState>('idle');
  const [errorMessage, setErrorMessage] = useState<string>('');

  const { data: providers, isLoading, error } = useProviders();

  const handleConnect = async (provider: Provider) => {
    if (!provider.isAvailable) {
      return;
    }

    setSelectedProvider(provider.id);
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
            provider: provider.id,
            providerName: provider.name,
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

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <LoadingState message="Loading providers..." />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background p-4">
        <ErrorState message="Failed to load providers" />
      </div>
    );
  }

  if (connectionState === 'success') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background p-4">
        <Card className="w-full max-w-md">
          <CardContent className="pt-6">
            <div className="text-center space-y-4">
              <div className="flex justify-center">
                <div className="rounded-full bg-green-100 dark:bg-green-900 p-3">
                  <Check className="h-8 w-8 text-green-600 dark:text-green-400" />
                </div>
              </div>
              <div>
                <h2 className="text-2xl font-bold">Successfully Connected!</h2>
                <p className="text-muted-foreground mt-2">
                  Your device has been connected and will start syncing data
                  shortly.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (connectionState === 'error') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background p-4">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle className="text-destructive">
              Connection Failed
            </CardTitle>
            <CardDescription>{errorMessage}</CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              className="w-full"
              onClick={() => {
                setConnectionState('idle');
                setSelectedProvider(null);
              }}
            >
              Try Again
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background p-4">
      <div className="max-w-4xl mx-auto py-8">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold mb-2">Connect Your Wearable</h1>
          <p className="text-muted-foreground">
            Choose a device or platform to connect and start tracking your
            health data
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {providers?.map((provider) => (
            <Card
              key={provider.id}
              className={`cursor-pointer transition-all hover:shadow-lg ${!provider.isAvailable ? 'opacity-50' : ''} ${selectedProvider === provider.id && connectionState === 'connecting' ? 'border-primary' : ''}`}
              onClick={() => handleConnect(provider)}
            >
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center mb-2">
                    <span className="text-2xl">{provider.name[0]}</span>
                  </div>
                  {!provider.isAvailable && (
                    <Badge variant="secondary">Coming Soon</Badge>
                  )}
                </div>
                <CardTitle className="text-xl">{provider.name}</CardTitle>
                <CardDescription className="line-clamp-2">
                  {provider.description}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-1 mb-4">
                  {provider.features.slice(0, 3).map((feature) => (
                    <Badge key={feature} variant="outline" className="text-xs">
                      {feature}
                    </Badge>
                  ))}
                  {provider.features.length > 3 && (
                    <Badge variant="outline" className="text-xs">
                      +{provider.features.length - 3} more
                    </Badge>
                  )}
                </div>
                <Button
                  className="w-full"
                  disabled={
                    !provider.isAvailable ||
                    (selectedProvider === provider.id &&
                      connectionState === 'connecting')
                  }
                  onClick={(e) => {
                    e.stopPropagation();
                    handleConnect(provider);
                  }}
                >
                  {selectedProvider === provider.id &&
                  connectionState === 'connecting' ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Connecting...
                    </>
                  ) : !provider.isAvailable ? (
                    'Coming Soon'
                  ) : (
                    'Connect'
                  )}
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>

        <div className="mt-8 text-center text-sm text-muted-foreground">
          <p>
            Your data is encrypted and secure. We only access the health metrics
            you explicitly authorize.
          </p>
        </div>
      </div>
    </div>
  );
}

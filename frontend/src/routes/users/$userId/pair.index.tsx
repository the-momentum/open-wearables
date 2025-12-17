import { createFileRoute } from '@tanstack/react-router';
import { motion, AnimatePresence } from 'motion/react';
import { ChevronRight, Check, AlertCircle, X, Lock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { WEARABLE_PROVIDERS } from '@/lib/constants/providers';
import { useOAuthConnect } from '@/hooks/use-oauth-connect';

export const Route = createFileRoute('/users/$userId/pair/')({
  component: PairWearablePage,
  validateSearch: (search: Record<string, unknown>) => ({
    redirect_url:
      typeof search.redirect_url === 'string' && search.redirect_url.length > 0
        ? search.redirect_url
        : undefined,
  }),
});

function PairWearablePage() {
  const { userId } = Route.useParams();
  const { redirect_url: redirectUrl } = Route.useSearch();

  const { connectionState, connectingProvider, error, connect, reset } =
    useOAuthConnect({ userId, redirectUrl });

  const connectingProviderData = connectingProvider
    ? WEARABLE_PROVIDERS.find((p) => p.id === connectingProvider)
    : null;

  const handleConnect = (providerId: string) => {
    if (connectingProvider === null) {
      connect(providerId);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-200 flex flex-col items-center justify-center p-6 relative overflow-hidden selection:bg-white/20">
      {/* Ambient Background Effect */}
      <div className="absolute top-0 left-0 w-full h-full bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(120,119,198,0.1),rgba(255,255,255,0))] pointer-events-none" />

      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="relative z-10 text-center mb-14 space-y-3"
      >
        <h1 className="text-4xl font-medium text-white tracking-tight">
          Connect a device
        </h1>
        <p className="text-lg text-zinc-400">Select your wearable platform</p>
      </motion.div>

      {/* Error notification */}
      <AnimatePresence>
        {connectionState === 'error' && error && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="relative z-10 mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/30 flex items-center gap-3 max-w-4xl w-full"
          >
            <AlertCircle className="w-5 h-5 text-red-400 shrink-0" />
            <p className="text-sm text-red-300 flex-1">{error}</p>
            <button
              onClick={reset}
              aria-label="Dismiss error"
              className="text-red-400/70 hover:text-red-300 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main content */}
      <AnimatePresence mode="wait">
        {connectionState === 'idle' && (
          <motion.div
            key="providers"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, y: -10 }}
            className="relative z-10 grid grid-cols-1 md:grid-cols-2 gap-6 w-full max-w-4xl"
          >
            {WEARABLE_PROVIDERS.filter((p) => p.isAvailable).map(
              (provider, index) => (
                <motion.button
                  key={provider.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.05, duration: 0.3 }}
                  onClick={() => handleConnect(provider.id)}
                  className="group relative flex flex-col items-center text-center p-10 rounded-2xl bg-zinc-900/40 border border-white/5 hover:bg-zinc-900/80 hover:border-white/10 transition-all duration-300 ease-out outline-none focus:ring-2 focus:ring-white/20"
                >
                  {/* Brand Logo */}
                  <div className="mb-8 flex items-center justify-center h-20 w-20 bg-white rounded-2xl shadow-lg shadow-black/20 group-hover:scale-105 transition-transform duration-300">
                    <img
                      src={provider.logoPath}
                      alt={`${provider.name} logo`}
                      className="w-14 h-14 object-contain"
                    />
                  </div>

                  {/* Text */}
                  <h3 className="text-xl font-medium text-white mb-3">
                    {provider.name}
                  </h3>
                  <p className="text-base text-zinc-500 max-w-xs leading-relaxed">
                    {provider.description}
                  </p>

                  {/* Connect indicator */}
                  <div className="mt-8 flex items-center gap-1.5 text-base font-medium text-zinc-200 group-hover:text-white transition-colors">
                    <span>Connect</span>
                    <ChevronRight className="w-4 h-4 stroke-[1.5]" />
                  </div>
                </motion.button>
              )
            )}
          </motion.div>
        )}

        {connectionState === 'connecting' && connectingProviderData && (
          <motion.div
            key="connecting"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0 }}
            className="relative z-10 text-center py-12"
          >
            <div
              role="status"
              aria-live="polite"
              aria-label={`Connecting to ${connectingProviderData.name}`}
              className="w-12 h-12 mx-auto mb-4 border-2 border-white/30 border-t-white rounded-full animate-spin"
            />
            <p className="text-zinc-400">
              Connecting to {connectingProviderData.name}...
            </p>
          </motion.div>
        )}

        {connectionState === 'success' && (
          <motion.div
            key="success"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ type: 'spring', stiffness: 200, damping: 15 }}
            className="relative z-10 text-center py-12"
          >
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{
                type: 'spring',
                stiffness: 200,
                damping: 12,
                delay: 0.1,
              }}
              className="w-16 h-16 mx-auto mb-4 rounded-full bg-green-500/20 flex items-center justify-center shadow-[0_0_30px_hsla(145,100%,50%,0.3)]"
            >
              <Check className="w-8 h-8 text-green-500" />
            </motion.div>
            <h2 className="text-xl font-medium text-white mb-2">Connected</h2>
            <p className="text-zinc-400 text-sm mb-6">
              Your device will start syncing shortly
            </p>
            <Button
              variant="ghost"
              onClick={reset}
              className="text-zinc-200 hover:text-white hover:bg-white/10"
            >
              Connect another device
            </Button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Footer Security */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3 }}
        className="mt-20 flex items-center gap-2 text-zinc-500 text-base font-normal opacity-80 hover:opacity-100 transition-opacity"
      >
        <Lock className="w-4 h-4 stroke-[1.5]" />
        <span>Your data is encrypted and secure</span>
      </motion.div>
    </div>
  );
}

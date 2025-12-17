import { createFileRoute } from '@tanstack/react-router';
import { motion } from 'motion/react';
import { X, RefreshCw, ExternalLink } from 'lucide-react';
import { WEARABLE_PROVIDERS } from '@/lib/constants/providers';

export const Route = createFileRoute('/users/$userId/pair/error')({
  component: PairErrorPage,
  validateSearch: (search: Record<string, unknown>) => ({
    provider: (search.provider as string) || undefined,
    error: (search.error as string) || undefined,
    redirect_url: (search.redirect_url as string) || undefined,
  }),
});

function PairErrorPage() {
  const { userId } = Route.useParams();
  const {
    provider: providerId,
    error,
    redirect_url: redirectUrl,
  } = Route.useSearch();

  const provider = providerId
    ? WEARABLE_PROVIDERS.find((p) => p.id === providerId)
    : null;

  const errorMessage =
    error || 'Something went wrong while connecting your device.';

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-200 flex flex-col items-center justify-center p-6 relative overflow-hidden selection:bg-red-500/20">
      {/* Ambient Background Effect */}
      <div className="absolute top-0 left-0 w-full h-full bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(239,68,68,0.15),rgba(255,255,255,0))] pointer-events-none" />

      <div className="relative z-10 w-full max-w-md flex flex-col items-center">
        {/* Error Icon */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          className="mb-8 relative"
        >
          <div className="absolute inset-0 bg-red-500/20 blur-xl rounded-full" />
          <div className="relative flex items-center justify-center h-24 w-24 bg-zinc-900 border border-zinc-800 rounded-full shadow-2xl">
            <div className="absolute inset-0 rounded-full border border-red-500/30 animate-[pulse-ring_2s_cubic-bezier(0.24,0,0.38,1)_infinite]" />
            <X className="w-10 h-10 text-red-400 stroke-[2.5]" />
          </div>
        </motion.div>

        {/* Text Content */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1], delay: 0.1 }}
          className="text-center space-y-3 mb-10"
        >
          <h1 className="text-3xl font-medium text-white tracking-tight">
            Connection failed
          </h1>
          <p className="text-lg text-zinc-400 leading-relaxed">
            {errorMessage}
          </p>
        </motion.div>

        {/* Failed Device Card */}
        {provider && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1], delay: 0.2 }}
            className="w-full bg-zinc-900/40 border border-white/10 rounded-2xl p-5 mb-8 flex items-center justify-between"
          >
            <div className="flex items-center gap-4">
              <div className="flex items-center justify-center h-12 w-12 bg-white rounded-xl shadow-lg shadow-black/20">
                <img
                  src={provider.logoPath}
                  alt={`${provider.name} logo`}
                  className="w-8 h-8 object-contain"
                />
              </div>
              <div className="flex flex-col">
                <span className="text-base font-medium text-white">
                  {provider.name}
                </span>
                <div className="flex items-center gap-1.5">
                  <span className="relative flex h-2 w-2">
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500" />
                  </span>
                  <span className="text-sm text-zinc-500">Failed</span>
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {/* Action Buttons */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1], delay: 0.2 }}
          className="w-full space-y-4"
        >
          <a
            href={`/users/${userId}/pair${redirectUrl ? `?redirect_url=${encodeURIComponent(redirectUrl)}` : ''}`}
            className="w-full py-3.5 px-4 bg-white hover:bg-zinc-200 text-zinc-950 text-base font-medium rounded-xl transition-all duration-200 focus:ring-2 focus:ring-white/20 outline-none flex items-center justify-center gap-2"
          >
            <RefreshCw className="w-4 h-4 stroke-[1.5]" />
            Try again
          </a>

          {redirectUrl && (
            <a
              href={redirectUrl}
              className="w-full py-3.5 px-4 bg-transparent border border-white/5 hover:bg-white/5 text-zinc-400 hover:text-white text-base font-medium rounded-xl transition-all duration-200 outline-none flex items-center justify-center gap-2"
            >
              Back to the app
              <ExternalLink className="w-4 h-4 stroke-[1.5]" />
            </a>
          )}
        </motion.div>
      </div>

      {/* Pulse ring animation keyframes */}
      <style>{`
        @keyframes pulse-ring {
          0% {
            transform: scale(0.8);
            box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7);
          }
          70% {
            transform: scale(1);
            box-shadow: 0 0 0 10px rgba(239, 68, 68, 0);
          }
          100% {
            transform: scale(0.8);
            box-shadow: 0 0 0 0 rgba(239, 68, 68, 0);
          }
        }
      `}</style>
    </div>
  );
}

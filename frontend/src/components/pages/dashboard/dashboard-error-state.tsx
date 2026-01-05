import { cn } from '@/lib/utils';

export interface DashboardErrorStateProps {
  onRetry: () => void;
  className?: string;
}

export function DashboardErrorState({
  onRetry,
  className,
}: DashboardErrorStateProps) {
  return (
    <div className={cn('p-8', className)}>
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-12 text-center">
        <p className="text-zinc-400 mb-4">
          Failed to load dashboard data. Please try again.
        </p>
        <button
          onClick={onRetry}
          className="px-4 py-2 bg-white text-black rounded-md text-sm font-medium hover:bg-zinc-200 transition-colors"
        >
          Retry
        </button>
      </div>
    </div>
  );
}

import { cn } from '@/lib/utils';

export interface DashboardLoadingStateProps {
  className?: string;
}

export function DashboardLoadingState({
  className,
}: DashboardLoadingStateProps) {
  return (
    <div className={cn('p-8', className)}>
      <div className="mb-6">
        <h1 className="text-2xl font-medium text-white">Dashboard</h1>
        <p className="text-sm text-zinc-500 mt-1">Your platform overview</p>
      </div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6"
          >
            <div className="animate-pulse space-y-3">
              <div className="h-4 w-24 bg-zinc-800 rounded" />
              <div className="h-8 w-16 bg-zinc-800 rounded" />
              <div className="h-3 w-32 bg-zinc-800/50 rounded" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

import { cn } from '@/lib/utils';

export interface DashboardLoadingStateProps {
  className?: string;
}

export function DashboardLoadingState({
  className,
}: DashboardLoadingStateProps) {
  return (
    <div className={cn('relative min-h-full p-6 md:p-8', className)}>
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 overflow-hidden"
      >
        <div className="absolute -left-32 top-0 h-72 w-72 rounded-full bg-[hsl(var(--primary)/0.08)] blur-3xl" />
        <div className="absolute right-0 top-32 h-72 w-72 rounded-full bg-[hsl(var(--secondary)/0.06)] blur-3xl" />
      </div>

      <div className="relative space-y-6">
        <div>
          <div className="mb-2 h-6 w-16 animate-pulse rounded-full bg-muted" />
          <div className="h-9 w-48 animate-pulse rounded-lg bg-muted" />
          <div className="mt-2 h-4 w-72 animate-pulse rounded bg-muted/60" />
        </div>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="rounded-2xl border border-border/60 bg-gradient-to-br from-card/80 to-card/40 p-6 backdrop-blur-xl"
            >
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="h-3 w-20 animate-pulse rounded bg-muted" />
                  <div className="h-10 w-10 animate-pulse rounded-xl bg-muted" />
                </div>
                <div className="h-9 w-24 animate-pulse rounded bg-muted" />
                <div className="flex items-center justify-between">
                  <div className="h-3 w-32 animate-pulse rounded bg-muted/60" />
                  <div className="h-5 w-12 animate-pulse rounded-full bg-muted/60" />
                </div>
                <div className="h-1 w-full animate-pulse rounded-full bg-muted/40" />
              </div>
            </div>
          ))}
        </div>

        <div className="grid gap-6 lg:grid-cols-7">
          <div className="h-80 animate-pulse rounded-2xl border border-border/60 bg-gradient-to-br from-card/80 to-card/40 lg:col-span-4" />
          <div className="h-80 animate-pulse rounded-2xl border border-border/60 bg-gradient-to-br from-card/80 to-card/40 lg:col-span-3" />
        </div>
      </div>
    </div>
  );
}

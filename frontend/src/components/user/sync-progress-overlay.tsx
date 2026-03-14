import { CheckCircle2, Loader2, XCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { SyncProgress } from '@/lib/api/types';

interface SyncProgressOverlayProps {
  progress: SyncProgress;
  className?: string;
}

/**
 * Inline progress indicator shown inside a ConnectionCard while a sync
 * is running.  Displays the current step, a small progress bar, and the
 * list of completed / errored providers.
 */
export function SyncProgressOverlay({
  progress,
  className,
}: SyncProgressOverlayProps) {
  if (!progress.active && progress.events.length === 0) return null;

  const pct =
    progress.totalProviders > 0
      ? Math.round(
          ((progress.completedProviders.length +
            progress.errorProviders.length) /
            progress.totalProviders) *
            100
        )
      : 0;

  const isTerminal = !progress.active && progress.events.length > 0;
  const hasErrors = progress.errorProviders.length > 0;
  const lastEvent = progress.events[progress.events.length - 1];
  const isError = lastEvent?.type === 'sync:error';

  return (
    <div className={cn('space-y-2', className)}>
      {/* Status line */}
      <div className="flex items-center gap-2">
        {progress.active ? (
          <Loader2 className="h-4 w-4 animate-spin text-primary shrink-0" />
        ) : isError || (isTerminal && hasErrors) ? (
          <XCircle className="h-4 w-4 text-destructive shrink-0" />
        ) : (
          <CheckCircle2 className="h-4 w-4 text-green-500 shrink-0" />
        )}

        <span className="text-sm text-muted-foreground truncate">
          {progress.message}
        </span>
      </div>

      {/* Progress bar (visible while active or just finished) */}
      {(progress.active || isTerminal) && progress.totalProviders > 0 && (
        <div className="h-1.5 bg-muted rounded-full overflow-hidden">
          <div
            className={cn(
              'h-full transition-all duration-500',
              isError
                ? 'bg-destructive'
                : isTerminal
                  ? 'bg-green-500'
                  : 'bg-primary'
            )}
            style={{ width: `${pct}%` }}
          />
        </div>
      )}

      {/* Provider pill list */}
      {progress.providers.length > 1 && (
        <div className="flex flex-wrap gap-1 pl-6">
          {progress.providers.map((p) => {
            const done = progress.completedProviders.includes(p);
            const err = progress.errorProviders.includes(p);
            const current = progress.currentProvider === p && progress.active;
            return (
              <span
                key={p}
                className={cn(
                  'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
                  done && 'bg-green-500/10 text-green-600',
                  err && 'bg-destructive/10 text-destructive',
                  current && 'bg-primary/10 text-primary',
                  !done && !err && !current && 'bg-muted text-muted-foreground'
                )}
              >
                {current && <Loader2 className="h-3 w-3 animate-spin" />}
                {done && <CheckCircle2 className="h-3 w-3" />}
                {err && <XCircle className="h-3 w-3" />}
                {p}
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
}

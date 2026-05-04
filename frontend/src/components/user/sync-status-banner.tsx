import { useMemo } from 'react';
import {
  Loader2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Activity,
  PlayCircle,
} from 'lucide-react';
import { useSyncStatusStream } from '@/hooks/api/use-sync-status';
import type { SyncStatusEvent } from '@/lib/api';
import { cn } from '@/lib/utils';

interface SyncStatusBannerProps {
  userId: string;
  className?: string;
}

const STAGE_LABELS: Record<string, string> = {
  queued: 'Queued',
  started: 'Starting',
  fetching: 'Fetching',
  processing: 'Processing',
  saving: 'Saving',
  completed: 'Completed',
  failed: 'Failed',
  cancelled: 'Cancelled',
};

const SOURCE_LABELS: Record<string, string> = {
  pull: 'Live Sync',
  webhook: 'Webhook',
  sdk: 'SDK Upload',
  backfill: 'Historical Backfill',
  xml_import: 'XML Import',
};

function ProgressBar({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(100, value * 100));
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
      <div
        className="h-full rounded-full bg-primary transition-all duration-500 ease-out"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

function ActiveSyncRow({ event }: { event: SyncStatusEvent }) {
  const stageLabel = STAGE_LABELS[event.stage] ?? event.stage;
  const sourceLabel = SOURCE_LABELS[event.source] ?? event.source;
  const itemsLabel =
    event.items_total !== null && event.items_processed !== null
      ? `${event.items_processed} / ${event.items_total}`
      : event.items_processed !== null
        ? `${event.items_processed} items`
        : null;

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-blue-200/60 bg-gradient-to-r from-blue-50/80 to-indigo-50/40 p-3 dark:border-blue-900/40 dark:from-blue-950/40 dark:to-indigo-950/20">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <Loader2 className="h-4 w-4 shrink-0 animate-spin text-blue-600 dark:text-blue-400" />
          <span className="font-medium capitalize truncate text-sm">
            {event.provider}
          </span>
          <span className="text-xs text-muted-foreground shrink-0">
            · {sourceLabel}
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-900/60 dark:text-blue-200">
            {stageLabel}
          </span>
          {itemsLabel && (
            <span className="text-xs text-muted-foreground tabular-nums">
              {itemsLabel}
            </span>
          )}
        </div>
      </div>
      {event.progress !== null && <ProgressBar value={event.progress} />}
      {event.message && (
        <p className="text-xs text-muted-foreground line-clamp-1">
          {event.message}
        </p>
      )}
    </div>
  );
}

function TerminalSyncRow({ event }: { event: SyncStatusEvent }) {
  const isSuccess = event.status === 'success';
  const isPartial = event.status === 'partial';
  const isFailed = event.status === 'failed';
  const isCancelled = event.status === 'cancelled';

  const Icon = isSuccess
    ? CheckCircle2
    : isPartial
      ? AlertTriangle
      : isCancelled
        ? XCircle
        : XCircle;

  const colorClasses = isSuccess
    ? 'text-emerald-600 dark:text-emerald-400'
    : isPartial
      ? 'text-amber-600 dark:text-amber-400'
      : 'text-rose-600 dark:text-rose-400';

  const bgClasses = isSuccess
    ? 'border-emerald-200/60 bg-emerald-50/60 dark:border-emerald-900/40 dark:bg-emerald-950/30'
    : isPartial
      ? 'border-amber-200/60 bg-amber-50/60 dark:border-amber-900/40 dark:bg-amber-950/30'
      : 'border-rose-200/60 bg-rose-50/60 dark:border-rose-900/40 dark:bg-rose-950/30';

  const sourceLabel = SOURCE_LABELS[event.source] ?? event.source;
  const statusLabel = isSuccess
    ? 'Completed'
    : isPartial
      ? 'Completed with warnings'
      : isFailed
        ? 'Failed'
        : 'Cancelled';

  return (
    <div
      className={cn(
        'flex items-center justify-between gap-3 rounded-lg border p-2.5',
        bgClasses
      )}
    >
      <div className="flex items-center gap-2 min-w-0">
        <Icon className={cn('h-4 w-4 shrink-0', colorClasses)} />
        <span className="font-medium capitalize truncate text-sm">
          {event.provider}
        </span>
        <span className="text-xs text-muted-foreground shrink-0">
          · {sourceLabel}
        </span>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <span className={cn('text-xs font-medium', colorClasses)}>
          {statusLabel}
        </span>
        {event.items_processed !== null && (
          <span className="text-xs text-muted-foreground tabular-nums">
            {event.items_processed} items
          </span>
        )}
      </div>
    </div>
  );
}

export function SyncStatusBanner({ userId, className }: SyncStatusBannerProps) {
  const { activeRuns, events, connected, error } = useSyncStatusStream(userId);

  const activeList = useMemo(
    () => Array.from(activeRuns.values()),
    [activeRuns]
  );

  const recentTerminal = useMemo(() => {
    const seen = new Set<string>();
    const out: SyncStatusEvent[] = [];
    for (const evt of events) {
      if (
        evt.status === 'success' ||
        evt.status === 'partial' ||
        evt.status === 'failed' ||
        evt.status === 'cancelled'
      ) {
        if (seen.has(evt.run_id)) continue;
        seen.add(evt.run_id);
        out.push(evt);
        if (out.length >= 3) break;
      }
    }
    return out;
  }, [events]);

  if (!activeList.length && !recentTerminal.length && !error) {
    return null;
  }

  return (
    <div
      className={cn(
        'rounded-xl border bg-card/50 p-4 shadow-sm backdrop-blur-sm',
        className
      )}
    >
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {activeList.length > 0 ? (
            <Activity className="h-4 w-4 animate-pulse text-blue-600 dark:text-blue-400" />
          ) : (
            <PlayCircle className="h-4 w-4 text-muted-foreground" />
          )}
          <h3 className="text-sm font-semibold">
            {activeList.length > 0
              ? `${activeList.length} sync${activeList.length === 1 ? '' : 's'} in progress`
              : 'Recent syncs'}
          </h3>
        </div>
        <div className="flex items-center gap-1.5">
          <span
            className={cn(
              'h-2 w-2 rounded-full',
              connected
                ? 'bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.6)]'
                : 'bg-muted-foreground/40'
            )}
            aria-label={connected ? 'Live' : 'Disconnected'}
          />
          <span className="text-xs text-muted-foreground">
            {connected ? 'Live' : 'Offline'}
          </span>
        </div>
      </div>

      {error && (
        <div className="mb-2 rounded-md border border-rose-200/60 bg-rose-50/60 p-2 text-xs text-rose-700 dark:border-rose-900/40 dark:bg-rose-950/30 dark:text-rose-300">
          {error}
        </div>
      )}

      <div className="flex flex-col gap-2">
        {activeList.map((evt) => (
          <ActiveSyncRow key={evt.run_id} event={evt} />
        ))}
        {recentTerminal.map((evt) => (
          <TerminalSyncRow key={evt.run_id} event={evt} />
        ))}
      </div>
    </div>
  );
}

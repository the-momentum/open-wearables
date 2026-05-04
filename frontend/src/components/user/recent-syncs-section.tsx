import { useMemo } from 'react';
import { History, RefreshCw } from 'lucide-react';
import { useRecentSyncs, useSyncRuns } from '@/hooks/api/use-sync-status';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import type { SyncRunSummary } from '@/lib/api';

interface RecentSyncsSectionProps {
  userId: string;
}

const SOURCE_LABELS: Record<string, string> = {
  pull: 'Live Sync',
  webhook: 'Webhook',
  sdk: 'SDK Upload',
  backfill: 'Historical Backfill',
  xml_import: 'XML Import',
};

const STATUS_BADGE: Record<string, string> = {
  success:
    'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300',
  partial:
    'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
  failed: 'bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300',
  cancelled: 'bg-zinc-200 text-zinc-700 dark:bg-zinc-800/60 dark:text-zinc-300',
  in_progress:
    'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
};

function formatDuration(start: string | null, end: string | null): string {
  if (!start || !end) return '—';
  const ms = new Date(end).getTime() - new Date(start).getTime();
  if (ms < 0 || !Number.isFinite(ms)) return '—';
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${m}m ${rem}s`;
}

function formatRelative(iso: string | null): string {
  if (!iso) return '—';
  const date = new Date(iso);
  const diff = Date.now() - date.getTime();
  if (diff < 0) return date.toLocaleString();
  const s = Math.floor(diff / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return date.toLocaleString();
}

function RunRow({ run }: { run: SyncRunSummary }) {
  const sourceLabel = SOURCE_LABELS[run.source] ?? run.source;
  const badgeClass = STATUS_BADGE[run.status] ?? STATUS_BADGE.in_progress;
  return (
    <div className="flex items-center justify-between gap-4 rounded-lg border bg-card/40 p-3">
      <div className="flex flex-col min-w-0 gap-0.5">
        <div className="flex items-center gap-2">
          <span className="font-medium capitalize text-sm">{run.provider}</span>
          <span className="text-xs text-muted-foreground">· {sourceLabel}</span>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>{formatRelative(run.last_update)}</span>
          {run.started_at && run.ended_at && (
            <>
              <span>·</span>
              <span>{formatDuration(run.started_at, run.ended_at)}</span>
            </>
          )}
          {run.items_processed !== null && (
            <>
              <span>·</span>
              <span className="tabular-nums">
                {run.items_processed}
                {run.items_total !== null ? ` / ${run.items_total}` : ''} items
              </span>
            </>
          )}
        </div>
        {run.error && (
          <p className="mt-1 text-xs text-rose-600 dark:text-rose-400 line-clamp-1">
            {run.error}
          </p>
        )}
      </div>
      <span
        className={cn(
          'shrink-0 rounded-full px-2.5 py-1 text-xs font-medium capitalize',
          badgeClass
        )}
      >
        {run.status.replace('_', ' ')}
      </span>
    </div>
  );
}

export function RecentSyncsSection({ userId }: RecentSyncsSectionProps) {
  const {
    data: runs,
    isLoading: isLoadingRuns,
    refetch: refetchRuns,
    isFetching: isFetchingRuns,
  } = useSyncRuns(userId, 30);
  const { refetch: refetchEvents } = useRecentSyncs(userId, 100, false);

  const sortedRuns = useMemo(() => runs ?? [], [runs]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <History className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-lg font-semibold">Recent Syncs</h2>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            refetchRuns();
            refetchEvents();
          }}
          disabled={isFetchingRuns}
          className="gap-2"
        >
          <RefreshCw
            className={cn('h-4 w-4', isFetchingRuns && 'animate-spin')}
          />
          Refresh
        </Button>
      </div>

      {isLoadingRuns ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-16 w-full rounded-lg" />
          ))}
        </div>
      ) : sortedRuns.length === 0 ? (
        <div className="rounded-lg border border-dashed bg-muted/20 p-8 text-center">
          <History className="mx-auto h-8 w-8 text-muted-foreground/40" />
          <p className="mt-2 text-sm text-muted-foreground">
            No sync activity in the last 24 hours.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {sortedRuns.map((run) => (
            <RunRow key={run.run_id} run={run} />
          ))}
        </div>
      )}
    </div>
  );
}

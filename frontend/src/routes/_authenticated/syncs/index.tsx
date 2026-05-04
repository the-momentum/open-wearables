import { createFileRoute, Link } from '@tanstack/react-router';
import { useState, useMemo } from 'react';
import { RefreshCw, History, Filter, X } from 'lucide-react';
import {
  useAllSyncRuns,
  type AllSyncRunsFilters,
} from '@/hooks/api/use-sync-status';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import type { SyncRunSummary } from '@/lib/api';

export const Route = createFileRoute('/_authenticated/syncs/')({
  component: SyncsPage,
});

const SOURCE_LABELS: Record<string, string> = {
  pull: 'Live Sync',
  webhook: 'Webhook',
  sdk: 'SDK Upload',
  backfill: 'Backfill',
  xml_import: 'XML Import',
};

const STATUS_BADGE: Record<string, string> = {
  success: 'bg-emerald-900/40 text-emerald-300',
  partial: 'bg-amber-900/40 text-amber-300',
  failed: 'bg-rose-900/40 text-rose-300',
  cancelled: 'bg-zinc-800/60 text-zinc-300',
  in_progress: 'bg-blue-900/40 text-blue-300',
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

const PAGE_SIZE = 50;

function SyncsPage() {
  const [filters, setFilters] = useState<AllSyncRunsFilters>({});
  const [userIdInput, setUserIdInput] = useState('');
  const [page, setPage] = useState(0);

  const activeFilters = useMemo(() => {
    const f: AllSyncRunsFilters = { ...filters };
    if (userIdInput.trim()) f.user_id = userIdInput.trim();
    return f;
  }, [filters, userIdInput]);

  const {
    data: runs,
    isLoading,
    isFetching,
    refetch,
  } = useAllSyncRuns(activeFilters, PAGE_SIZE * (page + 1));

  const paginatedRuns = useMemo(() => {
    if (!runs) return [];
    return runs.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  }, [runs, page]);

  const hasMore = (runs?.length ?? 0) > (page + 1) * PAGE_SIZE;

  const clearFilters = () => {
    setFilters({});
    setUserIdInput('');
    setPage(0);
  };

  const hasActiveFilters =
    !!userIdInput.trim() ||
    !!filters.provider ||
    !!filters.status ||
    !!filters.source;

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-medium text-white">Syncs</h1>
          <p className="text-sm text-zinc-500 mt-1">
            Monitor sync activity across all users and providers.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => refetch()}
          disabled={isFetching}
          className="gap-2"
        >
          <RefreshCw className={cn('h-4 w-4', isFetching && 'animate-spin')} />
          Refresh
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <Filter className="h-4 w-4 text-zinc-500" />
        <Input
          placeholder="Filter by user ID..."
          value={userIdInput}
          onChange={(e) => {
            setUserIdInput(e.target.value);
            setPage(0);
          }}
          className="w-72 h-8 text-sm bg-zinc-900 border-zinc-800"
        />
        <FilterSelect
          value={filters.provider}
          placeholder="Provider"
          options={['garmin', 'whoop', 'oura', 'polar', 'suunto', 'fitbit']}
          onChange={(v) => {
            setFilters((f) => ({ ...f, provider: v || undefined }));
            setPage(0);
          }}
        />
        <FilterSelect
          value={filters.status}
          placeholder="Status"
          options={['success', 'partial', 'failed', 'cancelled', 'in_progress']}
          onChange={(v) => {
            setFilters((f) => ({ ...f, status: v || undefined }));
            setPage(0);
          }}
        />
        <FilterSelect
          value={filters.source}
          placeholder="Source"
          options={['pull', 'webhook', 'sdk', 'backfill', 'xml_import']}
          onChange={(v) => {
            setFilters((f) => ({ ...f, source: v || undefined }));
            setPage(0);
          }}
        />
        {hasActiveFilters && (
          <Button
            variant="ghost"
            size="sm"
            onClick={clearFilters}
            className="h-8 gap-1 text-xs text-zinc-400"
          >
            <X className="h-3 w-3" />
            Clear
          </Button>
        )}
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full rounded-lg" />
          ))}
        </div>
      ) : paginatedRuns.length === 0 ? (
        <div className="rounded-lg border border-dashed bg-muted/20 p-12 text-center">
          <History className="mx-auto h-8 w-8 text-muted-foreground/40" />
          <p className="mt-2 text-sm text-muted-foreground">
            No sync activity found.
          </p>
        </div>
      ) : (
        <>
          <div className="rounded-lg border border-zinc-800 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800 bg-zinc-900/50 text-zinc-400 text-xs">
                  <th className="px-4 py-2.5 text-left font-medium">User ID</th>
                  <th className="px-4 py-2.5 text-left font-medium">
                    Provider
                  </th>
                  <th className="px-4 py-2.5 text-left font-medium">Source</th>
                  <th className="px-4 py-2.5 text-left font-medium">Status</th>
                  <th className="px-4 py-2.5 text-left font-medium">
                    Duration
                  </th>
                  <th className="px-4 py-2.5 text-left font-medium">
                    Items / Message
                  </th>
                  <th className="px-4 py-2.5 text-left font-medium">
                    Last Update
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/50">
                {paginatedRuns.map((run) => (
                  <SyncRow key={run.run_id} run={run} />
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between mt-4">
            <p className="text-xs text-zinc-500">
              Showing {page * PAGE_SIZE + 1}–
              {Math.min((page + 1) * PAGE_SIZE, runs?.length ?? 0)} of{' '}
              {runs?.length ?? 0}
            </p>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={!hasMore}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function SyncRow({ run }: { run: SyncRunSummary }) {
  const badgeClass = STATUS_BADGE[run.status] ?? STATUS_BADGE.in_progress;
  const sourceLabel = SOURCE_LABELS[run.source] ?? run.source;
  const shortUserId = run.user_id.slice(0, 8);

  return (
    <tr className="hover:bg-zinc-900/30 transition-colors">
      <td className="px-4 py-2.5">
        <Link
          to="/users/$userId"
          params={{ userId: run.user_id }}
          className="font-mono text-xs text-blue-400 hover:text-blue-300 hover:underline"
        >
          {shortUserId}…
        </Link>
      </td>
      <td className="px-4 py-2.5 capitalize">{run.provider}</td>
      <td className="px-4 py-2.5 text-zinc-400">{sourceLabel}</td>
      <td className="px-4 py-2.5">
        <span
          className={cn(
            'rounded-full px-2 py-0.5 text-xs font-medium capitalize',
            badgeClass
          )}
        >
          {run.status.replace('_', ' ')}
        </span>
      </td>
      <td className="px-4 py-2.5 text-zinc-400 tabular-nums">
        {formatDuration(run.started_at, run.ended_at)}
      </td>
      <td className="px-4 py-2.5 text-zinc-400 max-w-xs">
        {run.items_processed !== null ? (
          `${run.items_processed}${run.items_total !== null ? ` / ${run.items_total} items` : ' items'}`
        ) : run.message ? (
          <span className="truncate block text-xs">{run.message}</span>
        ) : (
          '—'
        )}
      </td>
      <td className="px-4 py-2.5 text-zinc-400">
        {formatRelative(run.last_update)}
      </td>
    </tr>
  );
}

function FilterSelect({
  value,
  placeholder,
  options,
  onChange,
}: {
  value: string | undefined;
  placeholder: string;
  options: string[];
  onChange: (val: string) => void;
}) {
  return (
    <select
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value)}
      className="h-8 rounded-md border border-zinc-800 bg-zinc-900 px-3 text-xs text-zinc-300 outline-none focus:ring-1 focus:ring-zinc-600"
    >
      <option value="">{placeholder}</option>
      {options.map((opt) => (
        <option key={opt} value={opt}>
          {opt.replace('_', ' ')}
        </option>
      ))}
    </select>
  );
}

import { createFileRoute, Link } from '@tanstack/react-router';
import { useState, useMemo } from 'react';
import { RefreshCw, History, Filter, X } from 'lucide-react';
import {
  useAllSyncRuns,
  type AllSyncRunsFilters,
} from '@/hooks/api/use-sync-status';
import { useOAuthProviders } from '@/hooks/api/use-oauth-providers';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import {
  SOURCE_LABELS,
  RUN_STATUS_CLASSES,
  formatRunDuration,
  formatRelative,
} from '@/lib/utils/sync-format';
import { ROUTES } from '@/lib/constants/routes';
import type { SyncRunSummary } from '@/lib/api';

export const Route = createFileRoute('/_authenticated/syncs/')({
  component: SyncsPage,
});

const PAGE_SIZE_OPTIONS = [10, 25, 50, 100] as const;
const DEFAULT_PAGE_SIZE = 50;
/** Must not exceed the backend's le= on GET /sync/runs. */
const MAX_ALL_RUNS_LIMIT = 10_000;

function SyncsPage() {
  const [filters, setFilters] = useState<AllSyncRunsFilters>({});
  const [userIdInput, setUserIdInput] = useState('');
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState<number>(DEFAULT_PAGE_SIZE);

  const { data: providerSettings } = useOAuthProviders();
  const providerOptions = useMemo(
    () => (providerSettings ?? []).map((p) => p.provider).sort(),
    [providerSettings]
  );

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
  } = useAllSyncRuns(
    activeFilters,
    Math.min(pageSize * (page + 1) + 1, MAX_ALL_RUNS_LIMIT)
  );

  const paginatedRuns = useMemo(() => {
    if (!runs) return [];
    return runs.slice(page * pageSize, (page + 1) * pageSize);
  }, [runs, page, pageSize]);

  const hasMore = (runs?.length ?? 0) > pageSize * (page + 1);

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
          options={providerOptions}
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
        <div className="ml-auto flex items-center gap-2">
          <span className="text-xs text-zinc-500">Per page:</span>
          <select
            value={pageSize}
            onChange={(e) => {
              setPageSize(Number(e.target.value));
              setPage(0);
            }}
            className="h-8 rounded-md border border-zinc-800 bg-zinc-900 px-3 text-xs text-zinc-300 outline-none focus:ring-1 focus:ring-zinc-600"
          >
            {PAGE_SIZE_OPTIONS.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </div>
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
              Showing {page * pageSize + 1}–
              {page * pageSize + paginatedRuns.length}
              {hasMore ? '+' : ''}
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
  const badgeClass =
    RUN_STATUS_CLASSES[run.status] ?? RUN_STATUS_CLASSES.in_progress;
  const sourceLabel = SOURCE_LABELS[run.source] ?? run.source;
  const shortUserId = run.user_id.slice(0, 8);

  return (
    <tr className="hover:bg-zinc-900/30 transition-colors">
      <td className="px-4 py-2.5">
        <Link
          to={ROUTES.user}
          params={{ userId: run.user_id }}
          className="font-mono text-xs text-blue-400 hover:text-blue-300 hover:underline"
        >
          {shortUserId}
          {run.user_id.length > 8 ? '…' : ''}
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
        {formatRunDuration(run.started_at, run.ended_at)}
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

import { useEffect, useMemo, useState } from 'react';
import { Database } from 'lucide-react';
import { useTimeSeries, useUserDataSummary } from '@/hooks/api/use-health';
import { useDateRange } from '@/hooks/use-date-range';
import { useCursorPagination } from '@/hooks/use-cursor-pagination';
import { CursorPagination } from '@/components/common/cursor-pagination';
import {
  DateRangeSelector,
  type DateRangeValue,
} from '@/components/ui/date-range-selector';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { formatDate, formatNumber } from '@/lib/utils/format';
import { formatLabel, formatSource, formatValue } from './utils';

interface TimeseriesExplorerProps {
  userId: string;
}

export function TimeseriesExplorer({ userId }: TimeseriesExplorerProps) {
  const { data: summary, isLoading: isSummaryLoading } =
    useUserDataSummary(userId);
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [range, setRange] = useState<DateRangeValue>(30);
  const { startDate, endDate } = useDateRange(range);
  const pagination = useCursorPagination();
  const { reset } = pagination;

  useEffect(() => {
    reset();
  }, [selectedType, range, reset]);

  const typeEntries = useMemo(
    () =>
      Object.entries(summary?.series_type_counts ?? {}).sort(
        (a, b) => b[1] - a[1]
      ),
    [summary]
  );

  const { data, isLoading, isFetching } = useTimeSeries(userId, {
    start_time: startDate,
    end_time: endDate,
    ...(selectedType ? { types: [selectedType] } : {}),
    limit: 50,
    cursor: pagination.currentCursor ?? undefined,
  });

  const samples = data?.data ?? [];
  const hasNextPage = data?.pagination?.has_more ?? false;
  const nextCursor = data?.pagination?.next_cursor ?? null;

  return (
    <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
      {/* Series type list */}
      <div className="rounded-xl border border-border/60 bg-card/40 p-3">
        <h3 className="mb-2 px-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Series Types
        </h3>
        {isSummaryLoading ? (
          <div className="space-y-2 px-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : (
          <nav className="max-h-[32rem] space-y-0.5 overflow-y-auto">
            <TypeButton
              label="All types"
              count={summary?.total_data_points ?? 0}
              isActive={selectedType === null}
              onClick={() => setSelectedType(null)}
            />
            {typeEntries.map(([code, count]) => (
              <TypeButton
                key={code}
                label={formatLabel(code)}
                count={count}
                isActive={selectedType === code}
                onClick={() => setSelectedType(code)}
              />
            ))}
          </nav>
        )}
      </div>

      {/* Samples table */}
      <div className="rounded-xl border border-border/60 bg-card/40 p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h3 className="text-sm font-medium text-foreground">
            {selectedType ? formatLabel(selectedType) : 'All Data Points'}
          </h3>
          <DateRangeSelector value={range} onChange={setRange} />
        </div>

        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : samples.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border/60 bg-muted/10 p-12 text-center">
            <Database className="mx-auto h-8 w-8 text-muted-foreground/40" />
            <p className="mt-2 text-sm text-muted-foreground">
              No data points in the last {range} days. Try a wider date range.
            </p>
          </div>
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Timestamp</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead className="text-right">Value</TableHead>
                  <TableHead>Unit</TableHead>
                  <TableHead>Source</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {samples.map((sample, i) => (
                  <TableRow key={`${sample.timestamp}-${sample.type}-${i}`}>
                    <TableCell className="whitespace-nowrap py-2.5 text-muted-foreground">
                      {formatDate(sample.timestamp)}
                    </TableCell>
                    <TableCell className="py-2.5">
                      {formatLabel(sample.type)}
                    </TableCell>
                    <TableCell className="py-2.5 text-right font-medium tabular-nums">
                      {formatValue(sample.value)}
                    </TableCell>
                    <TableCell className="py-2.5 text-muted-foreground">
                      {sample.unit}
                    </TableCell>
                    <TableCell className="py-2.5 text-muted-foreground">
                      {formatSource(sample.source)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <CursorPagination
              currentPage={pagination.currentPage}
              hasPrevPage={pagination.hasPrevPage}
              hasNextPage={hasNextPage}
              isFetching={isFetching}
              onPrevPage={pagination.goToPrevPage}
              onNextPage={() => pagination.goToNextPage(nextCursor)}
            />
          </>
        )}
      </div>
    </div>
  );
}

function TypeButton({
  label,
  count,
  isActive,
  onClick,
}: {
  label: string;
  count: number;
  isActive: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'flex w-full items-center justify-between gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors',
        isActive
          ? 'bg-muted text-foreground'
          : 'text-muted-foreground hover:bg-card/60 hover:text-foreground/90'
      )}
    >
      <span className="truncate">{label}</span>
      <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
        {formatNumber(count)}
      </span>
    </button>
  );
}

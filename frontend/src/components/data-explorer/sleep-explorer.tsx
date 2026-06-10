import { useEffect, useState } from 'react';
import { Moon } from 'lucide-react';
import { useSleepSessions } from '@/hooks/api/use-health';
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
import { formatDate, formatDuration, formatPercent } from '@/lib/utils/format';
import { formatSource } from './utils';

interface SleepExplorerProps {
  userId: string;
}

export function SleepExplorer({ userId }: SleepExplorerProps) {
  const [range, setRange] = useState<DateRangeValue>(90);
  const { startDate, endDate } = useDateRange(range);
  const pagination = useCursorPagination();
  const { reset } = pagination;

  useEffect(() => {
    reset();
  }, [range, reset]);

  const { data, isLoading, isFetching } = useSleepSessions(userId, {
    start_date: startDate,
    end_date: endDate,
    limit: 50,
    cursor: pagination.currentCursor ?? undefined,
  });

  const sessions = data?.data ?? [];

  return (
    <div className="rounded-xl border border-border/60 bg-card/40 p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-sm font-medium text-foreground">Sleep Sessions</h3>
        <DateRangeSelector value={range} onChange={setRange} />
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      ) : sessions.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border/60 bg-muted/10 p-12 text-center">
          <Moon className="mx-auto h-8 w-8 text-muted-foreground/40" />
          <p className="mt-2 text-sm text-muted-foreground">
            No sleep sessions in the last {range} days. Try a wider date range.
          </p>
        </div>
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Start</TableHead>
                <TableHead>End</TableHead>
                <TableHead>In Bed</TableHead>
                <TableHead>Asleep</TableHead>
                <TableHead>Efficiency</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Source</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sessions.map((session) => (
                <TableRow key={session.id}>
                  <TableCell className="whitespace-nowrap py-2.5 text-muted-foreground">
                    {formatDate(session.start_time)}
                  </TableCell>
                  <TableCell className="whitespace-nowrap py-2.5 text-muted-foreground">
                    {formatDate(session.end_time)}
                  </TableCell>
                  <TableCell className="py-2.5 tabular-nums">
                    {formatDuration(session.duration_seconds)}
                  </TableCell>
                  <TableCell className="py-2.5 tabular-nums">
                    {formatDuration(session.sleep_duration_seconds)}
                  </TableCell>
                  <TableCell className="py-2.5 tabular-nums">
                    {formatPercent(session.efficiency_percent)}
                  </TableCell>
                  <TableCell className="py-2.5">
                    {session.is_nap ? 'Nap' : 'Night'}
                  </TableCell>
                  <TableCell className="py-2.5 text-muted-foreground">
                    {formatSource(session.source)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <CursorPagination
            currentPage={pagination.currentPage}
            hasPrevPage={pagination.hasPrevPage}
            hasNextPage={data?.pagination?.has_more ?? false}
            isFetching={isFetching}
            onPrevPage={pagination.goToPrevPage}
            onNextPage={() =>
              pagination.goToNextPage(data?.pagination?.next_cursor ?? null)
            }
          />
        </>
      )}
    </div>
  );
}

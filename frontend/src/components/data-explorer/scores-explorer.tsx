import { useEffect, useState } from 'react';
import { Gauge } from 'lucide-react';
import { useHealthScores } from '@/hooks/api/use-health';
import { useDateRange } from '@/hooks/use-date-range';
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
import { Button } from '@/components/ui/button';
import { formatDate } from '@/lib/utils/format';
import { formatLabel, formatValue } from './utils';

const PAGE_SIZE = 50;

interface ScoresExplorerProps {
  userId: string;
}

export function ScoresExplorer({ userId }: ScoresExplorerProps) {
  const [range, setRange] = useState<DateRangeValue>(90);
  const [page, setPage] = useState(0);
  const { startDate, endDate } = useDateRange(range);

  useEffect(() => {
    setPage(0);
  }, [range]);

  const { data, isLoading, isFetching } = useHealthScores(userId, {
    start_date: startDate,
    end_date: endDate,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  });

  const scores = data?.data ?? [];
  const hasMore = data?.pagination?.has_more ?? false;

  return (
    <div className="rounded-xl border border-border/60 bg-card/40 p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-sm font-medium text-foreground">Health Scores</h3>
        <DateRangeSelector value={range} onChange={setRange} />
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      ) : scores.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border/60 bg-muted/10 p-12 text-center">
          <Gauge className="mx-auto h-8 w-8 text-muted-foreground/40" />
          <p className="mt-2 text-sm text-muted-foreground">
            No health scores in the last {range} days. Try a wider date range.
          </p>
        </div>
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Recorded</TableHead>
                <TableHead>Category</TableHead>
                <TableHead className="text-right">Score</TableHead>
                <TableHead>Qualifier</TableHead>
                <TableHead>Provider</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {scores.map((score) => (
                <TableRow key={score.id}>
                  <TableCell className="whitespace-nowrap py-2.5 text-muted-foreground">
                    {formatDate(score.recorded_at)}
                  </TableCell>
                  <TableCell className="py-2.5">
                    {formatLabel(score.category)}
                  </TableCell>
                  <TableCell className="py-2.5 text-right font-medium tabular-nums">
                    {formatValue(score.value)}
                  </TableCell>
                  <TableCell className="py-2.5 capitalize text-muted-foreground">
                    {score.qualifier ?? '—'}
                  </TableCell>
                  <TableCell className="py-2.5 text-muted-foreground">
                    {formatLabel(score.provider)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {(page > 0 || hasMore) && (
            <div className="mt-4 flex items-center justify-end gap-2 border-t border-border/60 pt-4">
              <Button
                variant="outline"
                size="sm"
                disabled={page === 0 || isFetching}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={!hasMore || isFetching}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

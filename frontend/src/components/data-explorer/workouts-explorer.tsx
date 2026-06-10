import { useEffect, useState } from 'react';
import { Dumbbell } from 'lucide-react';
import { useWorkouts } from '@/hooks/api/use-health';
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
import {
  formatCalories,
  formatDate,
  formatDistance,
  formatDuration,
  formatHeartRate,
} from '@/lib/utils/format';
import { formatLabel, formatSource } from './utils';

interface WorkoutsExplorerProps {
  userId: string;
}

export function WorkoutsExplorer({ userId }: WorkoutsExplorerProps) {
  const [range, setRange] = useState<DateRangeValue>(90);
  const { startDate, endDate } = useDateRange(range);
  const pagination = useCursorPagination();
  const { reset } = pagination;

  useEffect(() => {
    reset();
  }, [range, reset]);

  const { data, isLoading, isFetching } = useWorkouts(userId, {
    start_date: startDate,
    end_date: endDate,
    limit: 50,
    cursor: pagination.currentCursor ?? undefined,
    sort_order: 'desc',
  });

  const workouts = data?.data ?? [];

  return (
    <div className="rounded-xl border border-border/60 bg-card/40 p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-sm font-medium text-foreground">Workouts</h3>
        <DateRangeSelector value={range} onChange={setRange} />
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      ) : workouts.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border/60 bg-muted/10 p-12 text-center">
          <Dumbbell className="mx-auto h-8 w-8 text-muted-foreground/40" />
          <p className="mt-2 text-sm text-muted-foreground">
            No workouts in the last {range} days. Try a wider date range.
          </p>
        </div>
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Start</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Duration</TableHead>
                <TableHead>Distance</TableHead>
                <TableHead>Calories</TableHead>
                <TableHead>Avg HR</TableHead>
                <TableHead>Source</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {workouts.map((workout) => (
                <TableRow key={workout.id}>
                  <TableCell className="whitespace-nowrap py-2.5 text-muted-foreground">
                    {formatDate(workout.start_time)}
                  </TableCell>
                  <TableCell className="py-2.5">
                    {formatLabel(workout.type)}
                  </TableCell>
                  <TableCell className="py-2.5 tabular-nums">
                    {formatDuration(workout.duration_seconds)}
                  </TableCell>
                  <TableCell className="py-2.5 tabular-nums">
                    {formatDistance(workout.distance_meters)}
                  </TableCell>
                  <TableCell className="py-2.5 tabular-nums">
                    {formatCalories(workout.calories_kcal)}
                  </TableCell>
                  <TableCell className="py-2.5 tabular-nums">
                    {formatHeartRate(workout.avg_heart_rate_bpm)}
                  </TableCell>
                  <TableCell className="py-2.5 text-muted-foreground">
                    {formatSource(workout.source)}
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

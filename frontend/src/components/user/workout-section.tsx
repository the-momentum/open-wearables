import { useMemo, useState } from 'react';
import { format } from 'date-fns';
import { CartesianGrid, Line, LineChart, XAxis, YAxis } from 'recharts';
import {
  ChevronDown,
  ChevronUp,
  Dumbbell,
  Flame,
  Heart,
  MoveHorizontal,
  Timer,
} from 'lucide-react';
import { useWorkouts, useTimeSeries } from '@/hooks/api/use-health';
import { useCursorPagination } from '@/hooks/use-cursor-pagination';
import {
  useDateRangeDates,
  useAllTimeRangeTimestamp,
} from '@/hooks/use-date-range';
import type { DateRangeValue } from '@/components/ui/date-range-selector';
import { CursorPagination } from '@/components/common/cursor-pagination';
import { SectionHeader } from '@/components/common/section-header';
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from '@/components/ui/chart';
import { getWorkoutStyle } from '@/lib/utils/workout-styles';
import { formatDuration, formatCalories } from '@/lib/utils/format';
import { prepareHrChartData } from '@/lib/utils/timeseries';
import { HR_CHART_CONFIG } from '@/lib/utils/chart-config';
import {
  getWorkoutCategory,
  getWorkoutDetailFields,
  calculateWorkoutStats,
  dateToTimestamp,
} from '@/lib/utils/workout';
import type { EventRecordResponse } from '@/lib/api/types';

interface WorkoutSectionProps {
  userId: string;
  dateRange: DateRangeValue;
  onDateRangeChange: (value: DateRangeValue) => void;
}

// Expandable workout row with HR time series
function WorkoutRow({
  workout,
  userId,
}: {
  workout: EventRecordResponse;
  userId: string;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const style = getWorkoutStyle(workout.type || workout.category || '');
  const category = getWorkoutCategory(workout.type || workout.category || '');

  // Get workout start and end times
  const startTime = workout.start_time || workout.start_datetime || '';
  const endTime = workout.end_time || workout.end_datetime || '';

  // Fetch heart rate time series data when expanded
  const { data: hrData, isLoading: hrLoading } = useTimeSeries(userId, {
    start_time: startTime,
    end_time: endTime,
    types: ['heart_rate'],
    resolution: '1min',
    limit: 100,
  });

  // Prepare HR chart data using utility function
  const hrChartData = useMemo(() => prepareHrChartData(hrData?.data), [hrData]);

  // Get detail fields using utility function
  const detailFields = useMemo(
    () => getWorkoutDetailFields(workout, category),
    [workout, category]
  );

  const workoutDate = workout.start_time || workout.start_datetime;

  return (
    <div className="border border-zinc-800 rounded-lg overflow-hidden bg-zinc-900/30 hover:bg-zinc-900/50 transition-colors">
      {/* Main row - always visible */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-3 flex items-center gap-4 text-left"
      >
        {/* Workout type emoji */}
        <div
          className={`flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center text-xl ${style.bgColor}`}
        >
          {style.emoji}
        </div>

        {/* Workout info */}
        <div className="flex-1 min-w-0 flex items-center">
          {/* Type & Date */}
          <div className="w-32 flex-shrink-0">
            <p className="text-sm font-medium text-white">{style.label}</p>
            <p className="text-xs text-zinc-500">
              {workoutDate ? format(new Date(workoutDate), 'MMM d, yyyy') : '-'}
            </p>
          </div>

          {/* Stats - evenly spaced */}
          <div className="flex-1 flex items-center justify-around">
            {/* Duration */}
            <div className="flex items-center gap-2">
              <Timer className="h-4 w-4 text-zinc-500" />
              <div>
                <p className="text-sm font-medium text-white">
                  {formatDuration(workout.duration_seconds)}
                </p>
                <p className="text-xs text-zinc-500">Duration</p>
              </div>
            </div>

            {/* Calories */}
            <div className="flex items-center gap-2">
              <Flame className="h-4 w-4 text-orange-400" />
              <div>
                <p className="text-sm font-medium text-white">
                  {formatCalories(workout.calories_kcal)}
                </p>
                <p className="text-xs text-zinc-500">Calories</p>
              </div>
            </div>

            {/* Avg Heart Rate */}
            <div className="flex items-center gap-2">
              <Heart className="h-4 w-4 text-rose-400" />
              <div>
                <p className="text-sm font-medium text-white">
                  {workout.avg_heart_rate_bpm
                    ? `${Math.round(Number(workout.avg_heart_rate_bpm))} bpm`
                    : '-'}
                </p>
                <p className="text-xs text-zinc-500">Avg HR</p>
              </div>
            </div>
          </div>

          {/* Expand indicator */}
          <div className="w-8 flex-shrink-0 flex justify-end">
            {isExpanded ? (
              <ChevronUp className="h-5 w-5 text-zinc-400" />
            ) : (
              <ChevronDown className="h-5 w-5 text-zinc-400" />
            )}
          </div>
        </div>
      </button>

      {/* Expanded details */}
      {isExpanded && (
        <div className="px-4 pb-4 pt-2 border-t border-zinc-800 space-y-4">
          {/* Heart Rate During Workout Chart */}
          <div>
            <h4 className="text-xs font-medium text-zinc-400 mb-3 uppercase tracking-wider">
              Heart Rate During Workout
            </h4>
            {hrLoading ? (
              <div className="h-[160px] flex items-center justify-center">
                <div className="h-5 w-5 border-2 border-rose-500 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : hrChartData.length > 0 ? (
              <ChartContainer
                config={HR_CHART_CONFIG}
                className="h-[160px] w-full"
              >
                <LineChart
                  accessibilityLayer
                  data={hrChartData}
                  margin={{ left: 8, right: 8 }}
                >
                  <CartesianGrid vertical={false} strokeDasharray="3 3" />
                  <XAxis
                    dataKey="time"
                    tickLine={false}
                    axisLine={false}
                    tickMargin={8}
                    interval="preserveStartEnd"
                    tick={{ fill: '#71717a', fontSize: 10 }}
                  />
                  <YAxis
                    tickLine={false}
                    axisLine={false}
                    tickMargin={8}
                    tick={{ fill: '#71717a', fontSize: 10 }}
                    domain={['dataMin - 10', 'dataMax + 10']}
                    width={35}
                  />
                  <ChartTooltip
                    cursor={false}
                    content={<ChartTooltipContent />}
                  />
                  <Line
                    dataKey="hr"
                    type="monotone"
                    stroke="var(--color-hr)"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4, fill: 'var(--color-hr)' }}
                  />
                </LineChart>
              </ChartContainer>
            ) : (
              <p className="text-xs text-zinc-500 text-center py-4">
                No heart rate data available for this workout
              </p>
            )}
          </div>

          {/* Detail Fields */}
          {detailFields.length > 0 && (
            <div className="flex gap-6 pt-2 border-t border-zinc-800/50">
              {/* Left column */}
              <div className="flex-1 space-y-2">
                {detailFields
                  .slice(0, Math.ceil(detailFields.length / 2))
                  .map((field) => (
                    <div
                      key={field.label}
                      className="flex items-center justify-between py-1"
                    >
                      <span className="text-sm text-zinc-500">
                        {field.label}
                      </span>
                      <span className="text-sm font-medium text-white">
                        {field.value}
                      </span>
                    </div>
                  ))}
              </div>

              {/* Divider */}
              <div className="w-px bg-zinc-800" />

              {/* Right column */}
              <div className="flex-1 space-y-2">
                {detailFields
                  .slice(Math.ceil(detailFields.length / 2))
                  .map((field) => (
                    <div
                      key={field.label}
                      className="flex items-center justify-between py-1"
                    >
                      <span className="text-sm text-zinc-500">
                        {field.label}
                      </span>
                      <span className="text-sm font-medium text-white">
                        {field.value}
                      </span>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Loading skeleton
function WorkoutSectionSkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2, 3, 4, 5].map((i) => (
        <div
          key={i}
          className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30"
        >
          <div className="flex items-center gap-4">
            <div className="h-10 w-10 bg-zinc-800 rounded-lg animate-pulse" />
            <div className="flex-1 grid grid-cols-4 gap-4">
              <div className="space-y-2">
                <div className="h-4 w-20 bg-zinc-800 rounded animate-pulse" />
                <div className="h-3 w-16 bg-zinc-800/50 rounded animate-pulse" />
              </div>
              <div className="space-y-2">
                <div className="h-4 w-12 bg-zinc-800 rounded animate-pulse" />
                <div className="h-3 w-14 bg-zinc-800/50 rounded animate-pulse" />
              </div>
              <div className="space-y-2">
                <div className="h-4 w-16 bg-zinc-800 rounded animate-pulse" />
                <div className="h-3 w-12 bg-zinc-800/50 rounded animate-pulse" />
              </div>
              <div className="flex justify-end">
                <div className="h-5 w-5 bg-zinc-800 rounded animate-pulse" />
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

const PAGE_SIZE = 10;

export function WorkoutSection({
  userId,
  dateRange,
  onDateRangeChange,
}: WorkoutSectionProps) {
  // Cursor-based pagination for workouts
  const pagination = useCursorPagination();

  // Date range hooks
  const allTimeRange = useAllTimeRangeTimestamp();
  const { startDate, endDate } = useDateRangeDates(dateRange);

  // Fetch workouts for current page
  const {
    data: workoutsResponse,
    isLoading,
    isFetching,
  } = useWorkouts(userId, {
    ...allTimeRange,
    limit: PAGE_SIZE,
    cursor: pagination.currentCursor ?? undefined,
    sort_order: 'desc',
  });

  // Derive pagination state from response
  const nextCursor = workoutsResponse?.pagination?.next_cursor ?? null;
  const hasNextPage = workoutsResponse?.pagination?.has_more ?? false;

  const handleNextPage = () => pagination.goToNextPage(nextCursor);
  const handlePrevPage = pagination.goToPrevPage;

  // Fetch workouts for summary (with date filter, larger limit)
  const { data: summaryWorkouts, isLoading: summaryLoading } = useWorkouts(
    userId,
    {
      start_date: dateToTimestamp(startDate),
      end_date: dateToTimestamp(endDate),
      limit: 1000,
      sort_order: 'desc',
    }
  );

  // Calculate summary stats from date-filtered workouts
  const stats = useMemo(
    () => calculateWorkoutStats(summaryWorkouts?.data || []),
    [summaryWorkouts]
  );

  const workouts = workoutsResponse?.data || [];
  const hasData = workouts.length > 0 || (stats?.count ?? 0) > 0;

  return (
    <div className="space-y-6">
      {/* Summary Section */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
        <SectionHeader
          title="Summary"
          dateRange={dateRange}
          onDateRangeChange={onDateRangeChange}
        />

        <div className="p-6">
          {summaryLoading ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[1, 2, 3, 4].map((i) => (
                <div
                  key={i}
                  className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30"
                >
                  <div className="h-8 w-16 bg-zinc-800 rounded animate-pulse" />
                  <div className="h-3 w-20 bg-zinc-800/50 rounded animate-pulse mt-2" />
                </div>
              ))}
            </div>
          ) : stats ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {/* Workouts Count */}
              <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                <div className="flex items-center gap-3 mb-3">
                  <div className="p-2 bg-indigo-500/10 rounded-lg">
                    <Dumbbell className="h-5 w-5 text-indigo-400" />
                  </div>
                </div>
                <p className="text-2xl font-semibold text-white">
                  {stats.count}
                </p>
                <p className="text-xs text-zinc-500 mt-1">Workouts</p>
              </div>

              {/* Total Time */}
              <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                <div className="flex items-center gap-3 mb-3">
                  <div className="p-2 bg-sky-500/10 rounded-lg">
                    <Timer className="h-5 w-5 text-sky-400" />
                  </div>
                </div>
                <p className="text-2xl font-semibold text-white">
                  {formatDuration(stats.totalDuration)}
                </p>
                <p className="text-xs text-zinc-500 mt-1">Total Time</p>
              </div>

              {/* Calories */}
              <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                <div className="flex items-center gap-3 mb-3">
                  <div className="p-2 bg-orange-500/10 rounded-lg">
                    <Flame className="h-5 w-5 text-orange-400" />
                  </div>
                </div>
                <p className="text-2xl font-semibold text-white">
                  {Math.round(stats.totalCalories).toLocaleString()}
                </p>
                <p className="text-xs text-zinc-500 mt-1">Calories</p>
              </div>

              {/* Distance */}
              <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                <div className="flex items-center gap-3 mb-3">
                  <div className="p-2 bg-purple-500/10 rounded-lg">
                    <MoveHorizontal className="h-5 w-5 text-purple-400" />
                  </div>
                </div>
                <p className="text-2xl font-semibold text-white">
                  {(stats.totalDistance / 1000).toFixed(1)} km
                </p>
                <p className="text-xs text-zinc-500 mt-1">Distance</p>
              </div>
            </div>
          ) : (
            <p className="text-sm text-zinc-500 text-center py-4">
              No workouts in this period
            </p>
          )}
        </div>
      </div>

      {/* Workout List Section */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
        <SectionHeader
          title="All Workouts"
          rightContent={
            !isLoading && hasData ? (
              <span className="text-xs text-zinc-500">
                Page {pagination.currentPage}
              </span>
            ) : undefined
          }
        />

        <div className="p-6">
          {isLoading ? (
            <WorkoutSectionSkeleton />
          ) : !hasData ? (
            <p className="text-sm text-zinc-500 text-center py-8">
              No workout data available
            </p>
          ) : (
            <div className="space-y-4">
              {/* Workout List */}
              <div className="space-y-3">
                {workouts.map((workout) => (
                  <WorkoutRow
                    key={workout.id}
                    workout={workout}
                    userId={userId}
                  />
                ))}
              </div>

              {/* Pagination Controls */}
              <CursorPagination
                currentPage={pagination.currentPage}
                hasPrevPage={pagination.hasPrevPage}
                hasNextPage={hasNextPage}
                isFetching={isFetching}
                onPrevPage={handlePrevPage}
                onNextPage={handleNextPage}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

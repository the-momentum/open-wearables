import { useState, useMemo } from 'react';
import { format } from 'date-fns';
import {
  ChevronDown,
  ChevronUp,
  Dumbbell,
  Flame,
  Heart,
  MoveHorizontal,
  Timer,
} from 'lucide-react';
import { useWorkouts } from '@/hooks/api/use-health';
import {
  DateRangeSelector,
  type DateRangeValue,
} from '@/components/ui/date-range-selector';
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination';
import { getWorkoutStyle } from '@/lib/utils/workout-styles';
import type { EventRecordResponse } from '@/lib/api/types';

interface WorkoutSectionProps {
  userId: string;
  dateRange: DateRangeValue;
  onDateRangeChange: (value: DateRangeValue) => void;
}

// Define which fields to show for each workout category
type WorkoutCategory =
  | 'running'
  | 'cycling'
  | 'swimming'
  | 'strength'
  | 'cardio'
  | 'default';

interface FieldConfig {
  key: keyof EventRecordResponse;
  label: string;
  format: (value: unknown) => string;
}

// Field definitions
const FIELD_DEFINITIONS: Record<string, FieldConfig> = {
  start_time: {
    key: 'start_time',
    label: 'Start',
    format: (v) => (v ? format(new Date(v as string), 'h:mm a') : '-'),
  },
  end_time: {
    key: 'end_time',
    label: 'End',
    format: (v) => (v ? format(new Date(v as string), 'h:mm a') : '-'),
  },
  distance_meters: {
    key: 'distance_meters',
    label: 'Distance',
    format: (v) => {
      if (!v) return '-';
      const meters = Number(v);
      if (meters >= 1000) return `${(meters / 1000).toFixed(2)} km`;
      return `${Math.round(meters)} m`;
    },
  },
  steps_count: {
    key: 'steps_avg',
    label: 'Steps',
    format: (v) => (v ? Number(v).toLocaleString() : '-'),
  },
  heart_rate_avg: {
    key: 'heart_rate_avg',
    label: 'Avg HR',
    format: (v) => (v ? `${Math.round(Number(v))} bpm` : '-'),
  },
  heart_rate_max: {
    key: 'heart_rate_max',
    label: 'Max HR',
    format: (v) => (v ? `${Math.round(Number(v))} bpm` : '-'),
  },
  total_elevation_gain: {
    key: 'total_elevation_gain',
    label: 'Elevation',
    format: (v) => (v ? `${Math.round(Number(v))} m` : '-'),
  },
  average_speed: {
    key: 'average_speed',
    label: 'Avg Speed',
    format: (v) => (v ? `${Number(v).toFixed(1)} km/h` : '-'),
  },
  max_speed: {
    key: 'max_speed',
    label: 'Max Speed',
    format: (v) => (v ? `${Number(v).toFixed(1)} km/h` : '-'),
  },
  average_watts: {
    key: 'average_watts',
    label: 'Avg Power',
    format: (v) => (v ? `${Math.round(Number(v))} W` : '-'),
  },
  moving_time: {
    key: 'moving_time_seconds',
    label: 'Moving Time',
    format: (v) => {
      if (!v) return '-';
      const secs = Number(v);
      const mins = Math.floor(secs / 60);
      const hours = Math.floor(mins / 60);
      if (hours > 0) return `${hours}h ${mins % 60}m`;
      return `${mins}m`;
    },
  },
  source: {
    key: 'source',
    label: 'Source',
    format: (v) => {
      if (!v) return '-';
      const source = v as { provider?: string; device?: string };
      return source.provider || '-';
    },
  },
};

// Workout category field configurations
const WORKOUT_FIELD_CONFIG: Record<WorkoutCategory, string[]> = {
  running: [
    'start_time',
    'end_time',
    'distance_meters',
    'steps_count',
    'heart_rate_avg',
    'heart_rate_max',
    'total_elevation_gain',
    'average_speed',
    'source',
  ],
  cycling: [
    'start_time',
    'end_time',
    'distance_meters',
    'heart_rate_avg',
    'heart_rate_max',
    'total_elevation_gain',
    'average_speed',
    'max_speed',
    'average_watts',
    'source',
  ],
  swimming: [
    'start_time',
    'end_time',
    'distance_meters',
    'heart_rate_avg',
    'heart_rate_max',
    'moving_time',
    'source',
  ],
  strength: [
    'start_time',
    'end_time',
    'heart_rate_avg',
    'heart_rate_max',
    'source',
  ],
  cardio: [
    'start_time',
    'end_time',
    'heart_rate_avg',
    'heart_rate_max',
    'steps_count',
    'source',
  ],
  default: [
    'start_time',
    'end_time',
    'distance_meters',
    'heart_rate_avg',
    'heart_rate_max',
    'source',
  ],
};

// Map workout types to categories
function getWorkoutCategory(type: string): WorkoutCategory {
  const lowerType = type.toLowerCase();

  if (
    lowerType.includes('run') ||
    lowerType.includes('walk') ||
    lowerType.includes('hik')
  ) {
    return 'running';
  }
  if (lowerType.includes('cycl') || lowerType.includes('bik')) {
    return 'cycling';
  }
  if (lowerType.includes('swim')) {
    return 'swimming';
  }
  if (
    lowerType.includes('strength') ||
    lowerType.includes('weight') ||
    lowerType.includes('gym')
  ) {
    return 'strength';
  }
  if (
    lowerType.includes('cardio') ||
    lowerType.includes('hiit') ||
    lowerType.includes('aerobic')
  ) {
    return 'cardio';
  }
  return 'default';
}

function formatDuration(seconds: number | null | undefined): string {
  if (!seconds) return '-';
  const secs = Number(seconds);
  const hours = Math.floor(secs / 3600);
  const mins = Math.floor((secs % 3600) / 60);
  if (hours > 0) return `${hours}h ${mins}m`;
  return `${mins}m`;
}

function formatCalories(kcal: number | null | undefined): string {
  if (!kcal) return '-';
  return `${Math.round(Number(kcal))} kcal`;
}

// Expandable workout row
function WorkoutRow({ workout }: { workout: EventRecordResponse }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const style = getWorkoutStyle(workout.type || workout.category || '');
  const category = getWorkoutCategory(workout.type || workout.category || '');
  const fieldKeys = WORKOUT_FIELD_CONFIG[category];

  // Get fields that have actual data
  const fieldsWithData = fieldKeys
    .map((key) => FIELD_DEFINITIONS[key])
    .filter((field) => {
      if (!field) return false;
      const value = workout[field.key];
      return value !== null && value !== undefined && value !== '';
    });

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
                  {workout.heart_rate_avg
                    ? `${Math.round(Number(workout.heart_rate_avg))} bpm`
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
      {isExpanded && fieldsWithData.length > 0 && (
        <div className="px-4 pb-4 pt-2 border-t border-zinc-800">
          <div className="flex gap-6">
            {/* Left column */}
            <div className="flex-1 space-y-2">
              {fieldsWithData
                .slice(0, Math.ceil(fieldsWithData.length / 2))
                .map((field) => {
                  const value = workout[field.key];
                  return (
                    <div
                      key={field.key}
                      className="flex items-center justify-between py-1"
                    >
                      <span className="text-sm text-zinc-500">
                        {field.label}
                      </span>
                      <span className="text-sm font-medium text-white">
                        {field.format(value)}
                      </span>
                    </div>
                  );
                })}
            </div>

            {/* Divider */}
            <div className="w-px bg-zinc-800" />

            {/* Right column */}
            <div className="flex-1 space-y-2">
              {fieldsWithData
                .slice(Math.ceil(fieldsWithData.length / 2))
                .map((field) => {
                  const value = workout[field.key];
                  return (
                    <div
                      key={field.key}
                      className="flex items-center justify-between py-1"
                    >
                      <span className="text-sm text-zinc-500">
                        {field.label}
                      </span>
                      <span className="text-sm font-medium text-white">
                        {field.format(value)}
                      </span>
                    </div>
                  );
                })}
            </div>
          </div>
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
  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [cursorHistory, setCursorHistory] = useState<(string | null)[]>([null]);

  // Current cursor is based on page
  const currentCursor = cursorHistory[currentPage - 1] ?? null;

  // Wide date range to fetch "all" workouts (backend requires start/end dates)
  const allTimeRange = useMemo(() => {
    const start = new Date('2000-01-01');
    const end = new Date();
    return {
      start_date: Math.floor(start.getTime() / 1000).toString(),
      end_date: Math.floor(end.getTime() / 1000).toString(),
    };
  }, []);

  // Fetch workouts for current page
  const {
    data: workoutsResponse,
    isLoading,
    isFetching,
  } = useWorkouts(userId, {
    ...allTimeRange,
    limit: PAGE_SIZE,
    cursor: currentCursor ?? undefined,
    sort_order: 'desc',
  });

  // Store next cursor when we get new data
  const nextCursor = workoutsResponse?.pagination?.next_cursor ?? null;
  const hasNextPage = workoutsResponse?.pagination?.has_more ?? false;
  const hasPrevPage = currentPage > 1;

  const handleNextPage = () => {
    if (hasNextPage && nextCursor) {
      // Store the next cursor if we haven't visited this page yet
      if (cursorHistory.length === currentPage) {
        setCursorHistory((prev) => [...prev, nextCursor]);
      }
      setCurrentPage((p) => p + 1);
    }
  };

  const handlePrevPage = () => {
    if (hasPrevPage) {
      setCurrentPage((p) => p - 1);
    }
  };

  // Calculate date range for summary
  const { startDate, endDate } = useMemo(() => {
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - dateRange);
    return { startDate: start, endDate: end };
  }, [dateRange]);

  // Fetch workouts for summary (with date filter, larger limit)
  const { data: summaryWorkouts, isLoading: summaryLoading } = useWorkouts(
    userId,
    {
      start_date: Math.floor(startDate.getTime() / 1000).toString(),
      end_date: Math.floor(endDate.getTime() / 1000).toString(),
      limit: 100,
      sort_order: 'desc',
    }
  );

  // Calculate summary stats from date-filtered workouts
  const stats = useMemo(() => {
    const data = summaryWorkouts?.data || [];
    if (data.length === 0) return null;

    const totalDuration = data.reduce(
      (sum, w) => sum + (Number(w.duration_seconds) || 0),
      0
    );
    const totalCalories = data.reduce(
      (sum, w) => sum + (Number(w.calories_kcal) || 0),
      0
    );
    const totalDistance = data.reduce(
      (sum, w) => sum + (Number(w.distance_meters) || 0),
      0
    );

    return {
      count: data.length,
      totalDuration,
      totalCalories,
      totalDistance,
    };
  }, [summaryWorkouts]);

  const workouts = workoutsResponse?.data || [];
  const hasData = workouts.length > 0 || (stats?.count ?? 0) > 0;

  return (
    <div className="space-y-6">
      {/* Summary Section */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-zinc-800 flex items-center justify-between">
          <h3 className="text-sm font-medium text-white">Summary</h3>
          <DateRangeSelector value={dateRange} onChange={onDateRangeChange} />
        </div>

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
        <div className="px-6 py-4 border-b border-zinc-800 flex items-center justify-between">
          <h3 className="text-sm font-medium text-white">All Workouts</h3>
          {/* Pagination info */}
          {!isLoading && hasData && (
            <span className="text-xs text-zinc-500">Page {currentPage}</span>
          )}
        </div>

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
                  <WorkoutRow key={workout.id} workout={workout} />
                ))}
              </div>

              {/* Pagination Controls */}
              {(hasPrevPage || hasNextPage) && (
                <div className="pt-4 border-t border-zinc-800">
                  <Pagination>
                    <PaginationContent>
                      <PaginationItem>
                        <PaginationPrevious
                          onClick={handlePrevPage}
                          className={
                            !hasPrevPage || isFetching
                              ? 'pointer-events-none opacity-50'
                              : 'cursor-pointer'
                          }
                        />
                      </PaginationItem>
                      <PaginationItem>
                        <PaginationLink isActive>{currentPage}</PaginationLink>
                      </PaginationItem>
                      <PaginationItem>
                        <PaginationNext
                          onClick={handleNextPage}
                          className={
                            !hasNextPage || isFetching
                              ? 'pointer-events-none opacity-50'
                              : 'cursor-pointer'
                          }
                        />
                      </PaginationItem>
                    </PaginationContent>
                  </Pagination>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

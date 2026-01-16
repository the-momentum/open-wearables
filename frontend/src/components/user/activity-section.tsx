import { useMemo, useState } from 'react';
import { format } from 'date-fns';
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from 'recharts';
import {
  Activity,
  ChevronDown,
  ChevronUp,
  Flame,
  Footprints,
  Heart,
  Timer,
  TrendingUp,
  MoveHorizontal,
  Armchair,
} from 'lucide-react';
import { useActivitySummaries } from '@/hooks/api/use-health';
import { useCursorPagination } from '@/hooks/use-cursor-pagination';
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
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from '@/components/ui/chart';
import type { ActivitySummary } from '@/lib/api/types';

interface ActivitySectionProps {
  userId: string;
  dateRange: DateRangeValue;
  onDateRangeChange: (value: DateRangeValue) => void;
}

const DAYS_PER_PAGE = 10;

// Metric definitions for the summary cards
type MetricKey =
  | 'steps'
  | 'calories'
  | 'activeTime'
  | 'heartRate'
  | 'distance'
  | 'floors'
  | 'sedentary';

interface MetricDefinition {
  key: MetricKey;
  label: string;
  shortLabel: string;
  icon: React.ElementType;
  color: string;
  bgColor: string;
  glowColor: string;
  getValue: (stats: Stats) => number | null;
  formatValue: (value: number | null) => string;
  getChartValue: (summary: ActivitySummary) => number;
  unit: string;
}

interface Stats {
  totalSteps: number;
  avgSteps: number;
  totalCalories: number;
  avgCalories: number;
  totalDistance: number;
  totalActiveMinutes: number;
  totalFloorsClimbed: number;
  totalSedentaryMinutes: number;
  avgHeartRate: number | null;
  daysTracked: number;
}

const METRICS: MetricDefinition[] = [
  {
    key: 'steps',
    label: 'Total Steps',
    shortLabel: 'Steps',
    icon: Footprints,
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/10',
    glowColor: 'shadow-[0_0_15px_rgba(16,185,129,0.5)]',
    getValue: (stats) => stats.totalSteps,
    formatValue: formatNumber,
    getChartValue: (s) => s.steps || 0,
    unit: '',
  },
  {
    key: 'calories',
    label: 'Active Calories',
    shortLabel: 'Calories',
    icon: Flame,
    color: 'text-orange-400',
    bgColor: 'bg-orange-500/10',
    glowColor: 'shadow-[0_0_15px_rgba(249,115,22,0.5)]',
    getValue: (stats) => stats.totalCalories,
    formatValue: formatNumber,
    getChartValue: (s) => s.active_calories_kcal || 0,
    unit: 'kcal',
  },
  {
    key: 'activeTime',
    label: 'Active Time',
    shortLabel: 'Active',
    icon: Timer,
    color: 'text-sky-400',
    bgColor: 'bg-sky-500/10',
    glowColor: 'shadow-[0_0_15px_rgba(14,165,233,0.5)]',
    getValue: (stats) => stats.totalActiveMinutes,
    formatValue: formatMinutes,
    getChartValue: (s) => s.active_minutes || 0,
    unit: 'min',
  },
  {
    key: 'heartRate',
    label: 'Avg Heart Rate',
    shortLabel: 'Heart Rate',
    icon: Heart,
    color: 'text-rose-400',
    bgColor: 'bg-rose-500/10',
    glowColor: 'shadow-[0_0_15px_rgba(244,63,94,0.5)]',
    getValue: (stats) => stats.avgHeartRate,
    formatValue: (v) => (v != null ? Math.round(v).toString() : '-'),
    getChartValue: (s) => s.heart_rate?.avg_bpm || 0,
    unit: 'bpm',
  },
  {
    key: 'distance',
    label: 'Total Distance',
    shortLabel: 'Distance',
    icon: MoveHorizontal,
    color: 'text-purple-400',
    bgColor: 'bg-purple-500/10',
    glowColor: 'shadow-[0_0_15px_rgba(168,85,247,0.5)]',
    getValue: (stats) => stats.totalDistance,
    formatValue: formatDistance,
    getChartValue: (s) => (s.distance_meters || 0) / 1000,
    unit: 'km',
  },
  {
    key: 'floors',
    label: 'Floors Climbed',
    shortLabel: 'Floors',
    icon: TrendingUp,
    color: 'text-amber-400',
    bgColor: 'bg-amber-500/10',
    glowColor: 'shadow-[0_0_15px_rgba(245,158,11,0.5)]',
    getValue: (stats) => stats.totalFloorsClimbed,
    formatValue: formatNumber,
    getChartValue: (s) => s.floors_climbed || 0,
    unit: '',
  },
  {
    key: 'sedentary',
    label: 'Sedentary Time',
    shortLabel: 'Sedentary',
    icon: Armchair,
    color: 'text-zinc-400',
    bgColor: 'bg-zinc-500/10',
    glowColor: 'shadow-[0_0_15px_rgba(113,113,122,0.5)]',
    getValue: (stats) => stats.totalSedentaryMinutes,
    formatValue: formatMinutes,
    getChartValue: (s) => s.sedentary_minutes || 0,
    unit: 'min',
  },
];

// Map metric colors to hex for chart
const METRIC_CHART_COLORS: Record<MetricKey, string> = {
  steps: '#10b981',
  calories: '#f97316',
  activeTime: '#0ea5e9',
  heartRate: '#f43f5e',
  distance: '#a855f7',
  floors: '#f59e0b',
  sedentary: '#71717a',
};

function formatNumber(value: number | null): string {
  if (value === null) return '-';
  return value.toLocaleString();
}

function formatDistance(meters: number | null): string {
  if (meters === null) return '-';
  const km = meters / 1000;
  if (km >= 1) {
    return `${km.toFixed(1)} km`;
  }
  return `${Math.round(meters)} m`;
}

function formatMinutes(minutes: number | null): string {
  if (minutes === null) return '-';
  const hours = Math.floor(minutes / 60);
  const mins = Math.round(minutes % 60);
  if (hours === 0) return `${mins}m`;
  return `${hours}h ${mins}m`;
}

// Loading skeleton
function ActivitySectionSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30"
          >
            <div className="h-5 w-5 bg-zinc-800 rounded animate-pulse mb-3" />
            <div className="h-7 w-20 bg-zinc-800 rounded animate-pulse mb-1" />
            <div className="h-4 w-24 bg-zinc-800/50 rounded animate-pulse" />
          </div>
        ))}
      </div>
    </div>
  );
}

// Activity day row (expandable)
function ActivityDayRow({ summary }: { summary: ActivitySummary }) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Collect all available detail fields
  const detailFields = useMemo(() => {
    const fields: { label: string; value: string }[] = [];

    if (summary.distance_meters != null) {
      fields.push({
        label: 'Distance',
        value: formatDistance(summary.distance_meters),
      });
    }
    if (summary.floors_climbed != null) {
      fields.push({
        label: 'Floors Climbed',
        value: formatNumber(summary.floors_climbed),
      });
    }
    if (summary.elevation_meters != null) {
      fields.push({
        label: 'Elevation',
        value: `${Math.round(summary.elevation_meters)} m`,
      });
    }
    if (summary.total_calories_kcal != null) {
      fields.push({
        label: 'Total Calories',
        value: formatNumber(summary.total_calories_kcal),
      });
    }
    if (summary.sedentary_minutes != null) {
      fields.push({
        label: 'Sedentary Time',
        value: formatMinutes(summary.sedentary_minutes),
      });
    }
    if (summary.heart_rate?.max_bpm != null) {
      fields.push({
        label: 'Max Heart Rate',
        value: `${summary.heart_rate.max_bpm} bpm`,
      });
    }
    if (summary.heart_rate?.min_bpm != null) {
      fields.push({
        label: 'Min Heart Rate',
        value: `${summary.heart_rate.min_bpm} bpm`,
      });
    }
    if (summary.intensity_minutes?.light != null) {
      fields.push({
        label: 'Light Activity',
        value: formatMinutes(summary.intensity_minutes.light),
      });
    }
    if (summary.intensity_minutes?.moderate != null) {
      fields.push({
        label: 'Moderate Activity',
        value: formatMinutes(summary.intensity_minutes.moderate),
      });
    }
    if (summary.intensity_minutes?.vigorous != null) {
      fields.push({
        label: 'Vigorous Activity',
        value: formatMinutes(summary.intensity_minutes.vigorous),
      });
    }
    if (summary.source?.provider) {
      fields.push({ label: 'Source', value: summary.source.provider });
    }

    return fields;
  }, [summary]);

  const hasDetails = detailFields.length > 0;

  return (
    <div className="border border-zinc-800 rounded-lg overflow-hidden bg-zinc-900/30 hover:bg-zinc-900/50 transition-colors">
      {/* Main row - always visible */}
      <button
        onClick={() => hasDetails && setIsExpanded(!isExpanded)}
        className="w-full px-4 py-3 flex items-center text-left"
        disabled={!hasDetails}
      >
        {/* Date */}
        <div className="w-28 flex-shrink-0">
          <p className="text-sm font-medium text-white">
            {format(new Date(summary.date), 'EEE, MMM d')}
          </p>
          <p className="text-xs text-zinc-500">
            {format(new Date(summary.date), 'yyyy')}
          </p>
        </div>

        {/* Stats - evenly spaced */}
        <div className="flex-1 flex items-center justify-around">
          {/* Steps */}
          <div className="flex items-center gap-2">
            <Footprints className="h-4 w-4 text-emerald-400" />
            <div>
              <p className="text-sm font-medium text-white">
                {formatNumber(summary.steps)}
              </p>
              <p className="text-xs text-zinc-500">Steps</p>
            </div>
          </div>

          {/* Calories */}
          <div className="flex items-center gap-2">
            <Flame className="h-4 w-4 text-orange-400" />
            <div>
              <p className="text-sm font-medium text-white">
                {formatNumber(summary.active_calories_kcal)}
              </p>
              <p className="text-xs text-zinc-500">Calories</p>
            </div>
          </div>

          {/* Avg Heart Rate */}
          <div className="flex items-center gap-2">
            <Heart className="h-4 w-4 text-rose-400" />
            <div>
              <p className="text-sm font-medium text-white">
                {summary.heart_rate?.avg_bpm
                  ? `${Math.round(summary.heart_rate.avg_bpm)} bpm`
                  : '-'}
              </p>
              <p className="text-xs text-zinc-500">Avg HR</p>
            </div>
          </div>

          {/* Active Time */}
          <div className="flex items-center gap-2">
            <Timer className="h-4 w-4 text-sky-400" />
            <div>
              <p className="text-sm font-medium text-white">
                {formatMinutes(summary.active_minutes)}
              </p>
              <p className="text-xs text-zinc-500">Active</p>
            </div>
          </div>
        </div>

        {/* Expand indicator */}
        {hasDetails && (
          <div className="w-8 flex-shrink-0 flex justify-end">
            {isExpanded ? (
              <ChevronUp className="h-5 w-5 text-zinc-400" />
            ) : (
              <ChevronDown className="h-5 w-5 text-zinc-400" />
            )}
          </div>
        )}
      </button>

      {/* Expanded details */}
      {isExpanded && detailFields.length > 0 && (
        <div className="px-4 pb-4 pt-2 border-t border-zinc-800">
          <div className="flex gap-6">
            {/* Left column */}
            <div className="flex-1 space-y-2">
              {detailFields
                .slice(0, Math.ceil(detailFields.length / 2))
                .map((field) => (
                  <div
                    key={field.label}
                    className="flex items-center justify-between py-1"
                  >
                    <span className="text-sm text-zinc-500">{field.label}</span>
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
                    <span className="text-sm text-zinc-500">{field.label}</span>
                    <span className="text-sm font-medium text-white">
                      {field.value}
                    </span>
                  </div>
                ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export function ActivitySection({
  userId,
  dateRange,
  onDateRangeChange,
}: ActivitySectionProps) {
  // Cursor-based pagination for activity days
  const pagination = useCursorPagination();

  // Calculate date range for summary
  const { startDate, endDate } = useMemo(() => {
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - dateRange);
    return {
      startDate: start.toISOString(),
      endDate: end.toISOString(),
    };
  }, [dateRange]);

  // Wide date range for fetching activity days
  const allTimeRange = useMemo(() => {
    const start = new Date('2000-01-01');
    const end = new Date();
    return {
      start_date: start.toISOString(),
      end_date: end.toISOString(),
    };
  }, []);

  // Fetch activity summaries for summary stats (date range filtered)
  const { data: summaryData, isLoading: summaryLoading } = useActivitySummaries(
    userId,
    {
      start_date: startDate,
      end_date: endDate,
      limit: 100,
    }
  );

  // Fetch activity days with cursor-based pagination
  const {
    data: daysData,
    isLoading: daysLoading,
    isFetching,
  } = useActivitySummaries(userId, {
    ...allTimeRange,
    limit: DAYS_PER_PAGE,
    cursor: pagination.currentCursor ?? undefined,
  });

  // Derive pagination state from response
  const nextCursor = daysData?.pagination?.next_cursor ?? null;
  const hasNextPage = daysData?.pagination?.has_more ?? false;

  const handleNextPage = () => pagination.goToNextPage(nextCursor);
  const handlePrevPage = pagination.goToPrevPage;

  // Calculate aggregate statistics from date-range filtered data
  const stats = useMemo(() => {
    const summaries = summaryData?.data || [];
    if (summaries.length === 0) {
      return null;
    }

    // Sum totals
    const totalSteps = summaries.reduce((acc, s) => acc + (s.steps || 0), 0);
    const totalCalories = summaries.reduce(
      (acc, s) => acc + (s.active_calories_kcal || 0),
      0
    );
    const totalDistance = summaries.reduce(
      (acc, s) => acc + (s.distance_meters || 0),
      0
    );
    const totalActiveMinutes = summaries.reduce(
      (acc, s) => acc + (s.active_minutes || 0),
      0
    );
    const totalFloorsClimbed = summaries.reduce(
      (acc, s) => acc + (s.floors_climbed || 0),
      0
    );
    const totalSedentaryMinutes = summaries.reduce(
      (acc, s) => acc + (s.sedentary_minutes || 0),
      0
    );

    // Calculate averages
    const daysWithSteps = summaries.filter((s) => s.steps !== null).length;
    const daysWithCalories = summaries.filter(
      (s) => s.active_calories_kcal !== null
    ).length;

    // Heart rate stats (average of daily averages)
    const heartRates = summaries
      .map((s) => s.heart_rate?.avg_bpm)
      .filter((hr): hr is number => hr !== null);
    const avgHeartRate =
      heartRates.length > 0
        ? heartRates.reduce((a, b) => a + b, 0) / heartRates.length
        : null;

    return {
      totalSteps,
      avgSteps: daysWithSteps > 0 ? Math.round(totalSteps / daysWithSteps) : 0,
      totalCalories,
      avgCalories:
        daysWithCalories > 0 ? Math.round(totalCalories / daysWithCalories) : 0,
      totalDistance,
      totalActiveMinutes,
      totalFloorsClimbed,
      totalSedentaryMinutes,
      avgHeartRate,
      daysTracked: summaries.length,
    };
  }, [summaryData]);

  // Get displayed days from current page data
  const displayedDays = daysData?.data || [];
  const hasData = displayedDays.length > 0;

  // Selected metric for the chart
  const [selectedMetric, setSelectedMetric] = useState<MetricKey>('steps');

  // Get the selected metric definition
  const currentMetric =
    METRICS.find((m) => m.key === selectedMetric) || METRICS[0];

  // Prepare chart data from summary data (sorted by date ascending)
  const chartData = useMemo(() => {
    const summaries = summaryData?.data || [];
    if (summaries.length === 0) return [];

    return [...summaries]
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .map((s) => ({
        date: format(new Date(s.date), 'MMM d'),
        value: currentMetric.getChartValue(s),
      }));
  }, [summaryData, currentMetric]);

  return (
    <div className="space-y-6">
      {/* Summary Section */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-zinc-800 flex items-center justify-between">
          <h3 className="text-sm font-medium text-white">Activity Summary</h3>
          <DateRangeSelector value={dateRange} onChange={onDateRangeChange} />
        </div>

        <div className="p-6">
          {summaryLoading ? (
            <ActivitySectionSkeleton />
          ) : !stats ? (
            <p className="text-sm text-zinc-500 text-center py-4">
              No activity data in this period
            </p>
          ) : (
            <div className="space-y-6">
              {/* Clickable Metric Cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {METRICS.map((metric) => {
                  const Icon = metric.icon;
                  const isSelected = selectedMetric === metric.key;
                  return (
                    <button
                      key={metric.key}
                      onClick={() => setSelectedMetric(metric.key)}
                      className={`p-4 border rounded-lg bg-zinc-900/30 text-left transition-all duration-200 cursor-pointer
                        ${
                          isSelected
                            ? `border-zinc-600 ${metric.glowColor}`
                            : 'border-zinc-800 hover:border-zinc-700 hover:shadow-[0_0_10px_rgba(255,255,255,0.1)]'
                        }
                      `}
                    >
                      <div className="flex items-center gap-3 mb-3">
                        <div className={`p-2 ${metric.bgColor} rounded-lg`}>
                          <Icon className={`h-5 w-5 ${metric.color}`} />
                        </div>
                      </div>
                      <p className="text-2xl font-semibold text-white">
                        {metric.formatValue(metric.getValue(stats))}
                      </p>
                      <p className="text-xs text-zinc-500 mt-1">
                        {metric.label}
                      </p>
                    </button>
                  );
                })}
                {/* Days Tracked - non-clickable */}
                <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 bg-indigo-500/10 rounded-lg">
                      <Activity className="h-5 w-5 text-indigo-400" />
                    </div>
                  </div>
                  <p className="text-2xl font-semibold text-white">
                    {stats.daysTracked}
                  </p>
                  <p className="text-xs text-zinc-500 mt-1">Days Tracked</p>
                </div>
              </div>

              {/* Dynamic Chart for Selected Metric */}
              {chartData.length > 1 && (
                <div className="pt-4 border-t border-zinc-800">
                  <h4 className="text-sm font-medium text-white mb-4">
                    Daily {currentMetric.shortLabel}
                  </h4>
                  <ChartContainer
                    config={{
                      value: {
                        label: currentMetric.shortLabel,
                        color: METRIC_CHART_COLORS[selectedMetric],
                      },
                    }}
                    className="h-[200px] w-full"
                  >
                    <BarChart accessibilityLayer data={chartData}>
                      <CartesianGrid vertical={false} strokeDasharray="3 3" />
                      <XAxis
                        dataKey="date"
                        tickLine={false}
                        axisLine={false}
                        tickMargin={8}
                        interval="preserveStartEnd"
                        tick={{ fill: '#71717a', fontSize: 11 }}
                      />
                      <YAxis
                        tickLine={false}
                        axisLine={false}
                        tickMargin={8}
                        tick={{ fill: '#71717a', fontSize: 11 }}
                        tickFormatter={(value) =>
                          value >= 1000
                            ? `${(value / 1000).toFixed(0)}k`
                            : String(value)
                        }
                      />
                      <ChartTooltip
                        cursor={{ fill: 'rgba(255, 255, 255, 0.05)' }}
                        content={<ChartTooltipContent />}
                      />
                      <Bar
                        dataKey="value"
                        fill="var(--color-value)"
                        radius={[4, 4, 0, 0]}
                      />
                    </BarChart>
                  </ChartContainer>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Activity Days Section */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-zinc-800 flex items-center justify-between">
          <h3 className="text-sm font-medium text-white">Activity Days</h3>
          {!daysLoading && hasData && (
            <span className="text-xs text-zinc-500">
              Page {pagination.currentPage}
            </span>
          )}
        </div>

        <div className="p-6">
          {daysLoading ? (
            <div className="space-y-3">
              {[1, 2, 3, 4, 5].map((i) => (
                <div
                  key={i}
                  className="px-4 py-3 border border-zinc-800 rounded-lg bg-zinc-900/30"
                >
                  <div className="flex items-center">
                    <div className="w-28 flex-shrink-0">
                      <div className="h-5 w-20 bg-zinc-800 rounded animate-pulse" />
                      <div className="h-3 w-12 bg-zinc-800/50 rounded animate-pulse mt-1" />
                    </div>
                    <div className="flex-1 flex items-center justify-around">
                      {[1, 2, 3, 4].map((j) => (
                        <div key={j} className="flex items-center gap-2">
                          <div className="h-4 w-4 bg-zinc-800 rounded animate-pulse" />
                          <div>
                            <div className="h-4 w-12 bg-zinc-800 rounded animate-pulse" />
                            <div className="h-3 w-10 bg-zinc-800/50 rounded animate-pulse mt-1" />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : displayedDays.length === 0 ? (
            <p className="text-sm text-zinc-500 text-center py-8">
              No activity data available
            </p>
          ) : (
            <div className="space-y-4">
              {/* Activity Days List */}
              <div className="space-y-3">
                {displayedDays.map((summary) => (
                  <ActivityDayRow key={summary.date} summary={summary} />
                ))}
              </div>

              {/* Pagination Controls */}
              {(pagination.hasPrevPage || hasNextPage) && (
                <div className="pt-4 border-t border-zinc-800">
                  <Pagination>
                    <PaginationContent>
                      <PaginationItem>
                        <PaginationPrevious
                          onClick={handlePrevPage}
                          className={
                            !pagination.hasPrevPage || isFetching
                              ? 'pointer-events-none opacity-50'
                              : 'cursor-pointer'
                          }
                        />
                      </PaginationItem>
                      <PaginationItem>
                        <PaginationLink isActive>
                          {pagination.currentPage}
                        </PaginationLink>
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

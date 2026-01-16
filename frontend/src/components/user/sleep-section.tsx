import { useMemo, useState } from 'react';
import { format } from 'date-fns';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  XAxis,
  YAxis,
} from 'recharts';
import {
  Moon,
  Zap,
  Clock,
  BedDouble,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import {
  useSleepSessions,
  useSleepSummaries,
  useTimeSeries,
} from '@/hooks/api/use-health';
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
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart';
import type {
  SleepSession,
  SleepStagesSummary,
  SleepSummary,
} from '@/lib/api/types';

interface SleepSectionProps {
  userId: string;
  dateRange: DateRangeValue;
  onDateRangeChange: (value: DateRangeValue) => void;
}

const SESSIONS_PER_PAGE = 10;

// Color mapping for sleep stages
const STAGE_COLORS = {
  deep: 'bg-indigo-500',
  rem: 'bg-purple-500',
  light: 'bg-sky-400',
  awake: 'bg-zinc-500',
} as const;

const STAGE_LABELS = {
  deep: 'Deep',
  rem: 'REM',
  light: 'Light',
  awake: 'Awake',
} as const;

const sleepHrChartConfig = {
  hr: {
    label: 'Heart Rate (bpm)',
    color: '#f43f5e',
  },
  avgHr: {
    label: 'Avg HR (bpm)',
    color: '#f43f5e',
  },
} satisfies ChartConfig;

// Metric definitions for clickable sleep cards
type SleepMetricKey = 'efficiency' | 'duration';

interface SleepStats {
  avgDuration: number | null;
  avgEfficiency: number | null;
  nightsTracked: number;
  avgBedtime: number | null;
  stages: SleepStagesSummary | null;
  stagesTotal: number;
}

interface SleepMetricDefinition {
  key: SleepMetricKey;
  label: string;
  shortLabel: string;
  icon: React.ElementType;
  color: string;
  bgColor: string;
  glowColor: string;
  getValue: (stats: SleepStats) => number | null;
  formatValue: (value: number | null) => string;
  getChartValue: (summary: SleepSummary) => number;
  unit: string;
}

const SLEEP_METRICS: SleepMetricDefinition[] = [
  {
    key: 'efficiency',
    label: 'Avg Efficiency',
    shortLabel: 'Efficiency',
    icon: Zap,
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/10',
    glowColor: 'shadow-[0_0_15px_rgba(16,185,129,0.5)]',
    getValue: (stats) => stats.avgEfficiency,
    formatValue: (v) => (v != null ? `${Math.round(v)}%` : '-'),
    getChartValue: (s) => s.efficiency_percent || 0,
    unit: '%',
  },
  {
    key: 'duration',
    label: 'Avg Duration',
    shortLabel: 'Duration',
    icon: Moon,
    color: 'text-indigo-400',
    bgColor: 'bg-indigo-500/10',
    glowColor: 'shadow-[0_0_15px_rgba(99,102,241,0.5)]',
    getValue: (stats) => stats.avgDuration,
    formatValue: (v) => formatMinutes(v),
    getChartValue: (s) => s.duration_minutes || 0,
    unit: 'min',
  },
];

// Map sleep metric colors to hex for chart
const SLEEP_METRIC_CHART_COLORS: Record<SleepMetricKey, string> = {
  efficiency: '#10b981',
  duration: '#6366f1',
};

function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours === 0) return `${minutes}m`;
  return `${hours}h ${minutes}m`;
}

function formatMinutes(minutes: number | null): string {
  if (minutes === null) return '-';
  const hours = Math.floor(minutes / 60);
  const mins = Math.round(minutes % 60);
  if (hours === 0) return `${mins}m`;
  return `${hours}h ${mins}m`;
}

function formatBedtime(minutes: number | null): string {
  if (minutes === null) return '-';
  // Handle wrap-around for late nights
  const normalizedMinutes = minutes >= 1440 ? minutes - 1440 : minutes;
  const hours = Math.floor(normalizedMinutes / 60);
  const mins = Math.round(normalizedMinutes % 60);
  const period = hours >= 12 ? 'PM' : 'AM';
  const displayHours = hours > 12 ? hours - 12 : hours === 0 ? 12 : hours;
  return `${displayHours}:${mins.toString().padStart(2, '0')} ${period}`;
}

// Component for visualizing sleep stages as a horizontal bar
function SleepStagesBar({
  stages,
  className = '',
}: {
  stages: SleepStagesSummary | null;
  className?: string;
}) {
  if (!stages) {
    return (
      <div className={`h-2 bg-zinc-700 rounded-full ${className}`}>
        <div className="h-full w-full bg-zinc-600 rounded-full" />
      </div>
    );
  }

  const total =
    (stages.deep_minutes || 0) +
    (stages.rem_minutes || 0) +
    (stages.light_minutes || 0) +
    (stages.awake_minutes || 0);

  if (total === 0) {
    return (
      <div className={`h-2 bg-zinc-700 rounded-full ${className}`}>
        <div className="h-full w-full bg-zinc-600 rounded-full" />
      </div>
    );
  }

  const stageData = [
    {
      key: 'deep',
      minutes: stages.deep_minutes || 0,
      pct: ((stages.deep_minutes || 0) / total) * 100,
      color: STAGE_COLORS.deep,
      label: STAGE_LABELS.deep,
    },
    {
      key: 'rem',
      minutes: stages.rem_minutes || 0,
      pct: ((stages.rem_minutes || 0) / total) * 100,
      color: STAGE_COLORS.rem,
      label: STAGE_LABELS.rem,
    },
    {
      key: 'light',
      minutes: stages.light_minutes || 0,
      pct: ((stages.light_minutes || 0) / total) * 100,
      color: STAGE_COLORS.light,
      label: STAGE_LABELS.light,
    },
    {
      key: 'awake',
      minutes: stages.awake_minutes || 0,
      pct: ((stages.awake_minutes || 0) / total) * 100,
      color: STAGE_COLORS.awake,
      label: STAGE_LABELS.awake,
    },
  ];

  return (
    <div
      className={`h-2 bg-zinc-700 rounded-full overflow-hidden flex ${className}`}
    >
      {stageData.map(
        (stage) =>
          stage.pct > 0 && (
            <Tooltip key={stage.key}>
              <TooltipTrigger asChild>
                <div
                  className={`${stage.color} cursor-pointer hover:opacity-80 transition-opacity`}
                  style={{ width: `${stage.pct}%` }}
                />
              </TooltipTrigger>
              <TooltipContent>
                <p>
                  {stage.label}: {formatMinutes(stage.minutes)} (
                  {Math.round(stage.pct)}%)
                </p>
              </TooltipContent>
            </Tooltip>
          )
      )}
    </div>
  );
}

// Expandable sleep session row with HR time series
function SleepSessionRow({
  session,
  userId,
}: {
  session: SleepSession;
  userId: string;
}) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Fetch heart rate time series data when expanded
  const { data: hrData, isLoading: hrLoading } = useTimeSeries(userId, {
    start_time: session.start_time,
    end_time: session.end_time,
    types: ['heart_rate'],
    resolution: '5min',
    limit: 100,
  });

  // Prepare HR chart data
  const hrChartData = useMemo(() => {
    if (!hrData?.data?.length) return [];
    return hrData.data
      .filter((d) => d.type === 'heart_rate')
      .sort(
        (a, b) =>
          new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
      )
      .map((d) => ({
        time: format(new Date(d.timestamp), 'HH:mm'),
        hr: d.value,
      }));
  }, [hrData]);

  // Collect all available detail fields (expanded view)
  const detailFields = useMemo(() => {
    const fields: { label: string; value: string }[] = [];

    // Stage details
    if (session.stages?.deep_minutes != null) {
      fields.push({
        label: 'Deep Sleep',
        value: formatMinutes(session.stages.deep_minutes),
      });
    }
    if (session.stages?.rem_minutes != null) {
      fields.push({
        label: 'REM Sleep',
        value: formatMinutes(session.stages.rem_minutes),
      });
    }
    if (session.stages?.light_minutes != null) {
      fields.push({
        label: 'Light Sleep',
        value: formatMinutes(session.stages.light_minutes),
      });
    }
    if (session.stages?.awake_minutes != null) {
      fields.push({
        label: 'Time Awake',
        value: formatMinutes(session.stages.awake_minutes),
      });
    }

    // Source
    if (session.source?.provider) {
      fields.push({ label: 'Source', value: session.source.provider });
    }

    return fields;
  }, [session]);

  // Always expandable - we'll show HR chart even without detail fields
  const hasDetails = true;

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
          {session.is_nap && (
            <span className="text-[10px] font-medium px-1.5 py-0.5 bg-amber-500/20 text-amber-400 rounded">
              NAP
            </span>
          )}
          <div className="flex items-center gap-2">
            <p className="text-sm font-medium text-white">
              {format(new Date(session.start_time), 'EEE, MMM d')}
            </p>
          </div>
          <p className="text-xs text-zinc-500">
            {format(new Date(session.start_time), 'yyyy')}
          </p>
        </div>

        {/* Right side - Top: Stages bar, Bottom: Stats */}
        <div className="flex-1 flex flex-col gap-2 mx-4">
          {/* Top: Sleep Stages Bar */}
          <SleepStagesBar stages={session.stages} className="h-3 mb-4" />

          {/* Bottom: Stats - evenly spaced */}
          <div className="flex items-center justify-around">
            {/* Efficiency */}
            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-emerald-400" />
              <div>
                <p className="text-sm font-medium text-white">
                  {session.efficiency_percent != null
                    ? `${Math.round(session.efficiency_percent)}%`
                    : '-'}
                </p>
                <p className="text-xs text-zinc-500">Efficiency</p>
              </div>
            </div>

            {/* Duration */}
            <div className="flex items-center gap-2">
              <Moon className="h-4 w-4 text-indigo-400" />
              <div>
                <p className="text-sm font-medium text-white">
                  {formatDuration(session.duration_seconds)}
                </p>
                <p className="text-xs text-zinc-500">Duration</p>
              </div>
            </div>

            {/* Bedtime */}
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-sky-400" />
              <div>
                <p className="text-sm font-medium text-white">
                  {format(new Date(session.start_time), 'h:mm a')}
                </p>
                <p className="text-xs text-zinc-500">Bedtime</p>
              </div>
            </div>

            {/* Wake Time */}
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-amber-400" />
              <div>
                <p className="text-sm font-medium text-white">
                  {format(new Date(session.end_time), 'h:mm a')}
                </p>
                <p className="text-xs text-zinc-500">Wake</p>
              </div>
            </div>
          </div>
        </div>

        {/* Expand indicator */}
        {hasDetails && (
          <div className="w-8 flex-shrink-0 flex justify-end ml-2">
            {isExpanded ? (
              <ChevronUp className="h-5 w-5 text-zinc-400" />
            ) : (
              <ChevronDown className="h-5 w-5 text-zinc-400" />
            )}
          </div>
        )}
      </button>

      {/* Expanded details */}
      {isExpanded && (
        <div className="px-4 pb-4 pt-2 border-t border-zinc-800 space-y-4">
          {/* Heart Rate During Sleep Chart */}
          <div>
            <h4 className="text-xs font-medium text-zinc-400 mb-3 uppercase tracking-wider">
              Heart Rate During Sleep
            </h4>
            {hrLoading ? (
              <div className="h-[160px] flex items-center justify-center">
                <div className="h-5 w-5 border-2 border-rose-500 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : hrChartData.length > 0 ? (
              <ChartContainer
                config={sleepHrChartConfig}
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
                    domain={['dataMin - 5', 'dataMax + 5']}
                    width={35}
                  />
                  <ChartTooltip
                    cursor={false}
                    content={<ChartTooltipContent />}
                  />
                  <Line
                    dataKey="hr"
                    type="monotone"
                    stroke="var(--color-avgHr)"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4, fill: 'var(--color-avgHr)' }}
                  />
                </LineChart>
              </ChartContainer>
            ) : (
              <p className="text-xs text-zinc-500 text-center py-4">
                No heart rate data available for this session
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
function SleepSectionSkeleton() {
  return (
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
  );
}

function SessionsListSkeleton() {
  return (
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
              {[1, 2, 3].map((j) => (
                <div key={j} className="flex items-center gap-2">
                  <div className="h-4 w-4 bg-zinc-800 rounded animate-pulse" />
                  <div>
                    <div className="h-4 w-12 bg-zinc-800 rounded animate-pulse" />
                    <div className="h-3 w-10 bg-zinc-800/50 rounded animate-pulse mt-1" />
                  </div>
                </div>
              ))}
              <div className="w-24 h-2 bg-zinc-800 rounded-full animate-pulse" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export function SleepSection({
  userId,
  dateRange,
  onDateRangeChange,
}: SleepSectionProps) {
  // Cursor-based pagination for sleep sessions
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

  // Wide date range for fetching sleep sessions
  const allTimeRange = useMemo(() => {
    const start = new Date('2000-01-01');
    const end = new Date();
    return {
      start_date: start.toISOString(),
      end_date: end.toISOString(),
    };
  }, []);

  // Fetch sleep summaries for summary stats (date range filtered)
  const { data: sleepSummaries, isLoading: summaryLoading } = useSleepSummaries(
    userId,
    {
      start_date: startDate,
      end_date: endDate,
      limit: 100,
    }
  );

  // Fetch sleep sessions with cursor-based pagination
  const {
    data: sessionsData,
    isLoading: sessionsLoading,
    isFetching,
  } = useSleepSessions(userId, {
    ...allTimeRange,
    limit: SESSIONS_PER_PAGE,
    cursor: pagination.currentCursor ?? undefined,
  });

  // Derive pagination state from response
  const nextCursor = sessionsData?.pagination?.next_cursor ?? null;
  const hasNextPage = sessionsData?.pagination?.has_more ?? false;

  const handleNextPage = () => pagination.goToNextPage(nextCursor);
  const handlePrevPage = pagination.goToPrevPage;

  // Calculate aggregate statistics from date-range filtered summaries
  const stats = useMemo(() => {
    const summaries = sleepSummaries?.data || [];
    if (summaries.length === 0) {
      return null;
    }

    // Filter out null values for averaging
    const durations = summaries
      .map((s) => s.duration_minutes)
      .filter((d): d is number => d !== null);
    const efficiencies = summaries
      .map((s) => s.efficiency_percent)
      .filter((e): e is number => e !== null);

    // Aggregate sleep stages (calculate averages)
    const totalDeep = summaries.reduce(
      (acc, s) => acc + (s.stages?.deep_minutes || 0),
      0
    );
    const totalRem = summaries.reduce(
      (acc, s) => acc + (s.stages?.rem_minutes || 0),
      0
    );
    const totalLight = summaries.reduce(
      (acc, s) => acc + (s.stages?.light_minutes || 0),
      0
    );
    const totalAwake = summaries.reduce(
      (acc, s) => acc + (s.stages?.awake_minutes || 0),
      0
    );
    const nightCount = summaries.length;
    const avgDeep = nightCount > 0 ? totalDeep / nightCount : 0;
    const avgRem = nightCount > 0 ? totalRem / nightCount : 0;
    const avgLight = nightCount > 0 ? totalLight / nightCount : 0;
    const avgAwake = nightCount > 0 ? totalAwake / nightCount : 0;
    const avgStagesTotal = avgDeep + avgRem + avgLight + avgAwake;

    // Calculate average bedtime
    const bedtimes = summaries
      .map((s) => s.start_time)
      .filter((t): t is string => t !== null)
      .map((t) => {
        const date = new Date(t);
        // Convert to minutes from midnight, handling late night times
        let minutes = date.getHours() * 60 + date.getMinutes();
        // If before 6am, treat as previous day's evening
        if (minutes < 360) minutes += 1440;
        return minutes;
      });

    const avgBedtimeMinutes =
      bedtimes.length > 0
        ? bedtimes.reduce((a, b) => a + b, 0) / bedtimes.length
        : null;

    return {
      avgDuration:
        durations.length > 0
          ? durations.reduce((a, b) => a + b, 0) / durations.length
          : null,
      avgEfficiency:
        efficiencies.length > 0
          ? efficiencies.reduce((a, b) => a + b, 0) / efficiencies.length
          : null,
      nightsTracked: summaries.length,
      avgBedtime: avgBedtimeMinutes,
      // Use SleepStagesSummary format so we can reuse SleepStagesBar
      // Store averages (not totals) so tooltip shows avg per night
      stages:
        avgStagesTotal > 0
          ? {
              deep_minutes: avgDeep,
              rem_minutes: avgRem,
              light_minutes: avgLight,
              awake_minutes: avgAwake,
            }
          : null,
      stagesTotal: avgStagesTotal,
    };
  }, [sleepSummaries]);

  // Get displayed sessions from current page data
  const displayedSessions = sessionsData?.data || [];
  const hasData = displayedSessions.length > 0;

  // Selected metric for the chart (default to efficiency)
  const [selectedMetric, setSelectedMetric] =
    useState<SleepMetricKey>('efficiency');

  // Get the selected metric definition
  const currentMetric =
    SLEEP_METRICS.find((m) => m.key === selectedMetric) || SLEEP_METRICS[0];

  // Prepare chart data from summary data (sorted by date ascending)
  const chartData = useMemo(() => {
    const summaries = sleepSummaries?.data || [];
    if (summaries.length === 0) return [];

    return [...summaries]
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .map((s) => ({
        date: format(new Date(s.date), 'MMM d'),
        value: currentMetric.getChartValue(s),
      }));
  }, [sleepSummaries, currentMetric]);

  return (
    <div className="space-y-6">
      {/* Summary Section */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-zinc-800 flex items-center justify-between">
          <h3 className="text-sm font-medium text-white">Sleep Summary</h3>
          <DateRangeSelector value={dateRange} onChange={onDateRangeChange} />
        </div>

        <div className="p-6">
          {summaryLoading ? (
            <SleepSectionSkeleton />
          ) : !stats ? (
            <p className="text-sm text-zinc-500 text-center py-4">
              No sleep data in this period
            </p>
          ) : (
            <div className="space-y-6">
              {/* Summary Stats - Top Row */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {/* Nights Tracked - non-clickable */}
                <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 bg-purple-500/10 rounded-lg">
                      <BedDouble className="h-5 w-5 text-purple-400" />
                    </div>
                  </div>
                  <p className="text-2xl font-semibold text-white">
                    {stats.nightsTracked}
                  </p>
                  <p className="text-xs text-zinc-500 mt-1">Nights Tracked</p>
                </div>

                {/* Clickable Metric Cards */}
                {SLEEP_METRICS.map((metric) => {
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

                {/* Average Bedtime - non-clickable */}
                <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 bg-sky-500/10 rounded-lg">
                      <Clock className="h-5 w-5 text-sky-400" />
                    </div>
                  </div>
                  <p className="text-2xl font-semibold text-white">
                    {formatBedtime(stats.avgBedtime)}
                  </p>
                  <p className="text-xs text-zinc-500 mt-1">Avg Bedtime</p>
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
                        color: SLEEP_METRIC_CHART_COLORS[selectedMetric],
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
                          selectedMetric === 'duration'
                            ? `${Math.round(value / 60)}h`
                            : `${value}%`
                        }
                        domain={
                          selectedMetric === 'efficiency' ? [0, 100] : undefined
                        }
                        width={40}
                      />
                      <ChartTooltip
                        cursor={false}
                        content={
                          <ChartTooltipContent
                            formatter={(value) =>
                              selectedMetric === 'duration'
                                ? formatMinutes(Number(value))
                                : `${Math.round(Number(value))}%`
                            }
                          />
                        }
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

              {/* Sleep Stages Breakdown */}
              {stats.stages && stats.stagesTotal > 0 && (
                <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                  <h4 className="text-xs font-medium text-zinc-400 mb-4 uppercase tracking-wider">
                    Average Sleep Stages
                  </h4>
                  <div className="space-y-4">
                    {/* Visual bar - reusing SleepStagesBar component */}
                    <SleepStagesBar stages={stats.stages} className="h-3" />

                    {/* Legend */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                      {(['deep', 'rem', 'light', 'awake'] as const).map(
                        (stage) => {
                          const key =
                            `${stage}_minutes` as keyof typeof stats.stages;
                          const minutes = stats.stages![key] || 0;
                          const percent = (minutes / stats.stagesTotal) * 100;
                          return (
                            <div
                              key={stage}
                              className="flex items-center gap-2"
                            >
                              <div
                                className={`w-3 h-3 rounded-sm ${STAGE_COLORS[stage]}`}
                              />
                              <span className="text-xs text-zinc-300">
                                {STAGE_LABELS[stage]}
                              </span>
                              <span className="text-xs text-zinc-500 ml-auto">
                                {Math.round(percent)}%
                              </span>
                            </div>
                          );
                        }
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Sleep Sessions Section */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-zinc-800 flex items-center justify-between">
          <h3 className="text-sm font-medium text-white">Sleep Sessions</h3>
          {!sessionsLoading && hasData && (
            <span className="text-xs text-zinc-500">
              Page {pagination.currentPage}
            </span>
          )}
        </div>

        <div className="p-6">
          {sessionsLoading ? (
            <SessionsListSkeleton />
          ) : displayedSessions.length === 0 ? (
            <p className="text-sm text-zinc-500 text-center py-8">
              No sleep sessions available
            </p>
          ) : (
            <div className="space-y-4">
              {/* Sessions List */}
              <div className="space-y-3">
                {displayedSessions.map((session) => (
                  <SleepSessionRow
                    key={session.id}
                    session={session}
                    userId={userId}
                  />
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

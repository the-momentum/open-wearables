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
import { useDateRange, useAllTimeRange } from '@/hooks/use-date-range';
import type { DateRangeValue } from '@/components/ui/date-range-selector';
import { CursorPagination } from '@/components/common/cursor-pagination';
import { MetricCard } from '@/components/common/metric-card';
import { SectionHeader } from '@/components/common/section-header';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from '@/components/ui/chart';
import {
  formatDuration,
  formatMinutes,
  formatBedtime,
} from '@/lib/utils/format';
import {
  calculateSleepStats,
  getSleepSessionDetailFields,
  getSleepStageData,
  SLEEP_METRIC_CHART_COLORS,
  SLEEP_STAGE_COLORS,
  SLEEP_STAGE_LABELS,
  type SleepStats,
  type SleepStageKey,
} from '@/lib/utils/sleep';
import { prepareHrChartData } from '@/lib/utils/timeseries';
import { HR_CHART_CONFIG } from '@/lib/utils/chart-config';
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

// Metric definitions for clickable sleep cards (kept here due to Lucide icon imports)
type SleepMetricKey = 'efficiency' | 'duration';

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

// Component for visualizing sleep stages as a horizontal bar
function SleepStagesBar({
  stages,
  className = '',
}: {
  stages: SleepStagesSummary | null;
  className?: string;
}) {
  const stageData = getSleepStageData(stages);

  if (stageData.length === 0) {
    return (
      <div className={`h-2 bg-zinc-700 rounded-full ${className}`}>
        <div className="h-full w-full bg-zinc-600 rounded-full" />
      </div>
    );
  }

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

  // Prepare HR chart data using utility function
  const hrChartData = useMemo(() => prepareHrChartData(hrData?.data), [hrData]);

  // Get detail fields using utility function
  const detailFields = useMemo(
    () => getSleepSessionDetailFields(session),
    [session]
  );

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
              {format(new Date(session.end_time), 'EEE, MMM d')}
            </p>
          </div>
          <p className="text-xs text-zinc-500">
            {format(new Date(session.end_time), 'yyyy')}
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

  // Date range hooks
  const { startDate, endDate } = useDateRange(dateRange);
  const allTimeRange = useAllTimeRange();

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
  const stats = useMemo(
    () => calculateSleepStats(sleepSummaries?.data || []),
    [sleepSummaries]
  );

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
        <SectionHeader
          title="Sleep Summary"
          dateRange={dateRange}
          onDateRangeChange={onDateRangeChange}
        />

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
                <MetricCard
                  icon={BedDouble}
                  iconColor="text-purple-400"
                  iconBgColor="bg-purple-500/10"
                  value={String(stats.nightsTracked)}
                  label="Nights Tracked"
                />

                {/* Clickable Metric Cards */}
                {SLEEP_METRICS.map((metric) => (
                  <MetricCard
                    key={metric.key}
                    icon={metric.icon}
                    iconColor={metric.color}
                    iconBgColor={metric.bgColor}
                    value={metric.formatValue(metric.getValue(stats))}
                    label={metric.label}
                    isClickable
                    isSelected={selectedMetric === metric.key}
                    glowColor={metric.glowColor}
                    onClick={() => setSelectedMetric(metric.key)}
                  />
                ))}

                {/* Average Bedtime - non-clickable */}
                <MetricCard
                  icon={Clock}
                  iconColor="text-sky-400"
                  iconBgColor="bg-sky-500/10"
                  value={formatBedtime(stats.avgBedtime)}
                  label="Avg Bedtime"
                />
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
                                className={`w-3 h-3 rounded-sm ${SLEEP_STAGE_COLORS[stage as SleepStageKey]}`}
                              />
                              <span className="text-xs text-zinc-300">
                                {SLEEP_STAGE_LABELS[stage as SleepStageKey]}
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
        <SectionHeader
          title="Sleep Sessions"
          rightContent={
            !sessionsLoading && hasData ? (
              <span className="text-xs text-zinc-500">
                Page {pagination.currentPage}
              </span>
            ) : undefined
          }
        />

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

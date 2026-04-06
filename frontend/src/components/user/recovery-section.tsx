import { useMemo, useState } from 'react';
import { format } from 'date-fns';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  XAxis,
  YAxis,
} from 'recharts';
import {
  Heart,
  Activity,
  Moon,
  Brain,
  ChevronDown,
  ChevronUp,
  Calendar,
} from 'lucide-react';
import { useRecoverySummaries } from '@/hooks/api/use-health';
import { useCursorPagination } from '@/hooks/use-cursor-pagination';
import { useDateRange, useAllTimeRange } from '@/hooks/use-date-range';
import type { DateRangeValue } from '@/components/ui/date-range-selector';
import { CursorPagination } from '@/components/common/cursor-pagination';
import { MetricCard } from '@/components/common/metric-card';
import { SourceBadge } from '@/components/common/source-badge';
import { SectionHeader } from '@/components/common/section-header';
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from '@/components/ui/chart';
import { formatHeartRate, formatDuration } from '@/lib/utils/format';
import type { RecoverySummary } from '@/lib/api/types';

interface RecoverySectionProps {
  userId: string;
  dateRange: DateRangeValue;
  onDateRangeChange: (value: DateRangeValue) => void;
}

const DAYS_PER_PAGE = 10;

// Score → color mapping (green above 70, amber 40-70, red below 40)
function scoreColor(score: number | null): string {
  if (score === null) return 'text-zinc-500';
  if (score >= 70) return 'text-emerald-400';
  if (score >= 40) return 'text-amber-400';
  return 'text-rose-400';
}

function scoreBgBar(score: number | null): string {
  if (score === null) return '#52525b';
  if (score >= 70) return '#10b981';
  if (score >= 40) return '#f59e0b';
  return '#f43f5e';
}

interface RecoveryStats {
  daysTracked: number;
  avgScore: number | null;
  avgHrv: number | null;
  avgRhr: number | null;
  avgSleepEfficiency: number | null;
}

function calculateStats(summaries: RecoverySummary[]): RecoveryStats | null {
  if (summaries.length === 0) return null;

  const scores = summaries
    .map((s) => s.recovery_score)
    .filter((s): s is number => s !== null);
  const hrvs = summaries
    .map((s) => s.avg_hrv_sdnn_ms)
    .filter((v): v is number => v !== null);
  const rhrs = summaries
    .map((s) => s.resting_heart_rate_bpm)
    .filter((v): v is number => v !== null);
  const efficiencies = summaries
    .map((s) => s.sleep_efficiency_percent)
    .filter((v): v is number => v !== null);

  const avg = (arr: number[]) =>
    arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : null;

  return {
    daysTracked: summaries.length,
    avgScore: scores.length ? Math.round(avg(scores)!) : null,
    avgHrv: hrvs.length ? Math.round(avg(hrvs)! * 10) / 10 : null,
    avgRhr: rhrs.length ? Math.round(avg(rhrs)!) : null,
    avgSleepEfficiency: efficiencies.length
      ? Math.round(avg(efficiencies)!)
      : null,
  };
}

// Circular score gauge (SVG donut)
function ScoreGauge({ score }: { score: number | null }) {
  const r = 38;
  const circ = 2 * Math.PI * r;
  const pct = score !== null ? score / 100 : 0;
  const dashArray = `${pct * circ} ${circ}`;
  const color =
    score === null
      ? '#52525b'
      : score >= 70
        ? '#10b981'
        : score >= 40
          ? '#f59e0b'
          : '#f43f5e';

  return (
    <div className="flex flex-col items-center justify-center">
      <svg width="96" height="96" viewBox="0 0 96 96">
        {/* Track */}
        <circle
          cx="48"
          cy="48"
          r={r}
          fill="none"
          stroke="#27272a"
          strokeWidth="8"
        />
        {/* Arc — starts at 12 o'clock (-90°) */}
        <circle
          cx="48"
          cy="48"
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeDasharray={dashArray}
          strokeLinecap="round"
          transform="rotate(-90 48 48)"
          style={{ transition: 'stroke-dasharray 0.6s ease' }}
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className={`text-2xl font-bold ${scoreColor(score)}`}>
          {score !== null ? score : '—'}
        </span>
        <span className="text-[10px] text-zinc-500 uppercase tracking-wider">
          score
        </span>
      </div>
    </div>
  );
}

// Expandable day row showing component breakdown
function RecoveryDayRow({ summary }: { summary: RecoverySummary }) {
  const [expanded, setExpanded] = useState(false);

  const components = summary.component_scores;
  const weights = summary.applied_weights;

  const componentList = components
    ? Object.entries(components).map(([key, score]) => ({
        key,
        label:
          key === 'hrv_score'
            ? 'HRV'
            : key === 'rhr_score'
              ? 'Resting HR'
              : 'Sleep',
        score,
        weight: weights?.[key] ?? null,
      }))
    : [];

  return (
    <div className="border border-zinc-800 rounded-lg overflow-hidden bg-zinc-900/30 hover:bg-zinc-900/50 transition-colors">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 flex items-center text-left"
      >
        {/* Date */}
        <div className="w-28 flex-shrink-0">
          <div className="flex items-center gap-1 mb-0.5">
            {summary.source?.provider && (
              <SourceBadge provider={summary.source.provider} />
            )}
          </div>
          <p className="text-sm font-medium text-white">
            {format(new Date(summary.date), 'EEE, MMM d')}
          </p>
          <p className="text-xs text-zinc-500">
            {format(new Date(summary.date), 'yyyy')}
          </p>
        </div>

        {/* Score gauge */}
        <div className="w-16 flex-shrink-0 relative flex items-center justify-center">
          <ScoreGauge score={summary.recovery_score} />
        </div>

        {/* Metrics */}
        <div className="flex-1 flex items-center justify-around mx-4">
          <div className="flex items-center gap-2">
            <Brain className="h-4 w-4 text-violet-400" />
            <div>
              <p className="text-sm font-medium text-white">
                {summary.avg_hrv_sdnn_ms !== null
                  ? `${summary.avg_hrv_sdnn_ms.toFixed(1)} ms`
                  : '—'}
              </p>
              <p className="text-xs text-zinc-500">HRV (SDNN)</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Heart className="h-4 w-4 text-rose-400" />
            <div>
              <p className="text-sm font-medium text-white">
                {formatHeartRate(summary.resting_heart_rate_bpm)}
              </p>
              <p className="text-xs text-zinc-500">Resting HR</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Moon className="h-4 w-4 text-indigo-400" />
            <div>
              <p className="text-sm font-medium text-white">
                {summary.sleep_efficiency_percent !== null
                  ? `${Math.round(summary.sleep_efficiency_percent)}%`
                  : '—'}
              </p>
              <p className="text-xs text-zinc-500">Sleep Eff.</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-sky-400" />
            <div>
              <p className="text-sm font-medium text-white">
                {formatDuration(summary.sleep_duration_seconds)}
              </p>
              <p className="text-xs text-zinc-500">Sleep</p>
            </div>
          </div>
        </div>

        <div className="w-6 flex-shrink-0 flex justify-end">
          {expanded ? (
            <ChevronUp className="h-4 w-4 text-zinc-500" />
          ) : (
            <ChevronDown className="h-4 w-4 text-zinc-500" />
          )}
        </div>
      </button>

      {/* Component breakdown */}
      {expanded && (
        <div className="px-4 pb-4 pt-3 border-t border-zinc-800 space-y-3">
          <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wider">
            Score Breakdown
          </h4>
          {componentList.length > 0 ? (
            <div className="space-y-2">
              {componentList.map(({ key, label, score, weight }) => (
                <div key={key} className="flex items-center gap-3">
                  <span className="text-xs text-zinc-400 w-20">{label}</span>
                  <div className="flex-1 h-2 bg-zinc-800 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{
                        width: `${score}%`,
                        backgroundColor: scoreBgBar(score),
                      }}
                    />
                  </div>
                  <span
                    className={`text-sm font-medium w-8 text-right ${scoreColor(score)}`}
                  >
                    {score}
                  </span>
                  {weight !== null && (
                    <span className="text-xs text-zinc-600 w-10 text-right">
                      {Math.round(weight * 100)}%
                    </span>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-zinc-500">
              {summary.recovery_score === null
                ? 'No physiological data available for this day'
                : 'Component breakdown unavailable'}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function RecoverySectionSkeleton() {
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

function DayListSkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2, 3, 4, 5].map((i) => (
        <div
          key={i}
          className="px-4 py-3 border border-zinc-800 rounded-lg bg-zinc-900/30"
        >
          <div className="flex items-center gap-4">
            <div className="w-28 space-y-1">
              <div className="h-4 w-20 bg-zinc-800 rounded animate-pulse" />
              <div className="h-3 w-12 bg-zinc-800/50 rounded animate-pulse" />
            </div>
            <div className="w-16 h-16 bg-zinc-800 rounded-full animate-pulse" />
            <div className="flex-1 flex justify-around">
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
  );
}

export function RecoverySection({
  userId,
  dateRange,
  onDateRangeChange,
}: RecoverySectionProps) {
  const pagination = useCursorPagination();
  const { startDate, endDate } = useDateRange(dateRange);
  const allTimeRange = useAllTimeRange();

  // Summary stats from the date-range window
  const { data: summaryData, isLoading: summaryLoading } = useRecoverySummaries(
    userId,
    {
      start_date: startDate,
      end_date: endDate,
      limit: 100,
    }
  );

  // Paginated day list
  const {
    data: pageData,
    isLoading: pageLoading,
    isFetching,
  } = useRecoverySummaries(userId, {
    ...allTimeRange,
    limit: DAYS_PER_PAGE,
    cursor: pagination.currentCursor ?? undefined,
  });

  const nextCursor = pageData?.pagination?.next_cursor ?? null;
  const hasNextPage = pageData?.pagination?.has_more ?? false;

  const stats = useMemo(
    () => calculateStats(summaryData?.data ?? []),
    [summaryData]
  );

  const chartData = useMemo(() => {
    const summaries = summaryData?.data ?? [];
    return [...summaries]
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .map((s) => ({
        date: format(new Date(s.date), 'MMM d'),
        score: s.recovery_score,
        fill: scoreBgBar(s.recovery_score),
      }));
  }, [summaryData]);

  const displayedDays = pageData?.data ?? [];

  return (
    <div className="space-y-6">
      {/* Summary card */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
        <SectionHeader
          title="Recovery Summary"
          dateRange={dateRange}
          onDateRangeChange={onDateRangeChange}
        />

        <div className="p-6">
          {summaryLoading ? (
            <RecoverySectionSkeleton />
          ) : !stats ? (
            <p className="text-sm text-zinc-500 text-center py-4">
              No recovery data in this period
            </p>
          ) : (
            <div className="space-y-6">
              {/* Metric cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <MetricCard
                  icon={Calendar}
                  iconColor="text-zinc-400"
                  iconBgColor="bg-zinc-500/10"
                  value={String(stats.daysTracked)}
                  label="Days Tracked"
                />
                <MetricCard
                  icon={Heart}
                  iconColor="text-emerald-400"
                  iconBgColor="bg-emerald-500/10"
                  value={stats.avgScore !== null ? String(stats.avgScore) : '—'}
                  label="Avg Recovery Score"
                />
                <MetricCard
                  icon={Brain}
                  iconColor="text-violet-400"
                  iconBgColor="bg-violet-500/10"
                  value={stats.avgHrv !== null ? `${stats.avgHrv} ms` : '—'}
                  label="Avg HRV (SDNN)"
                />
                <MetricCard
                  icon={Activity}
                  iconColor="text-rose-400"
                  iconBgColor="bg-rose-500/10"
                  value={formatHeartRate(stats.avgRhr)}
                  label="Avg Resting HR"
                />
              </div>

              {/* Score trend chart */}
              {chartData.length > 1 && (
                <div className="pt-4 border-t border-zinc-800">
                  <h4 className="text-sm font-medium text-white mb-4">
                    Daily Recovery Score
                  </h4>
                  <ChartContainer
                    config={{
                      score: { label: 'Recovery Score', color: '#10b981' },
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
                        domain={[0, 100]}
                        tickLine={false}
                        axisLine={false}
                        tickMargin={8}
                        tick={{ fill: '#71717a', fontSize: 11 }}
                        width={32}
                      />
                      <ReferenceLine
                        y={70}
                        stroke="#3f3f46"
                        strokeDasharray="4 4"
                        label={{
                          value: '70',
                          position: 'insideTopRight',
                          fill: '#71717a',
                          fontSize: 10,
                        }}
                      />
                      <ChartTooltip
                        cursor={false}
                        content={
                          <ChartTooltipContent
                            formatter={(value) => `${value} / 100`}
                          />
                        }
                      />
                      <Bar
                        dataKey="score"
                        radius={[4, 4, 0, 0]}
                        /* per-bar color via cell fill */
                        fill="#10b981"
                        isAnimationActive={false}
                      />
                    </BarChart>
                  </ChartContainer>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Day-by-day list */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
        <SectionHeader
          title="Recovery Days"
          rightContent={
            !pageLoading && displayedDays.length > 0 ? (
              <span className="text-xs text-zinc-500">
                Page {pagination.currentPage}
              </span>
            ) : undefined
          }
        />

        <div className="p-6">
          {pageLoading ? (
            <DayListSkeleton />
          ) : displayedDays.length === 0 ? (
            <p className="text-sm text-zinc-500 text-center py-8">
              No recovery data available
            </p>
          ) : (
            <div className="space-y-4">
              <div className="space-y-3">
                {displayedDays.map((day) => (
                  <RecoveryDayRow key={day.date} summary={day} />
                ))}
              </div>
              <CursorPagination
                currentPage={pagination.currentPage}
                hasPrevPage={pagination.hasPrevPage}
                hasNextPage={hasNextPage}
                isFetching={isFetching}
                onPrevPage={pagination.goToPrevPage}
                onNextPage={() => pagination.goToNextPage(nextCursor)}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

import { useMemo, useState } from 'react';
import { format } from 'date-fns';
import { Bar, BarChart, CartesianGrid, Legend, XAxis, YAxis } from 'recharts';
import {
  Activity,
  ChevronDown,
  ChevronUp,
  Heart,
  Scale,
  Thermometer,
} from 'lucide-react';
import { useBodySummariesDaily, useBodySummary } from '@/hooks/api/use-health';
import { useCursorPagination } from '@/hooks/use-cursor-pagination';
import { useAllTimeRange, useDateRange } from '@/hooks/use-date-range';
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
import {
  BODY_COMPOSITION_KEYS,
  BODY_METRICS,
  BODY_RECENT_READING_KEYS,
  BODY_VITALS_KEYS,
  formatBloodPressure,
  formatHeartRate,
  formatHrv,
  formatLastUpdated,
  getBmiCategory,
  type BodyMetricDefinition,
  type BodyMetricKey,
} from '@/lib/utils/body';
import {
  formatBmi,
  formatHeight,
  formatPercentDecimal,
  formatTemperature,
  formatWeight,
} from '@/lib/utils/format';
import type { BodyDailySummary } from '@/lib/api/types';

interface BodySectionProps {
  userId: string;
  dateRange: DateRangeValue;
  onDateRangeChange: (value: DateRangeValue) => void;
}

const DAYS_PER_PAGE = 10;

// ============================================================================
// Helpers
// ============================================================================

const METRIC_BY_KEY: Record<BodyMetricKey, BodyMetricDefinition> =
  BODY_METRICS.reduce(
    (acc, m) => {
      acc[m.key] = m;
      return acc;
    },
    {} as Record<BodyMetricKey, BodyMetricDefinition>
  );

function getDetailFields(
  row: BodyDailySummary
): { label: string; value: string }[] {
  const fields: { label: string; value: string }[] = [];
  if (row.weight_kg !== null)
    fields.push({ label: 'Weight', value: formatWeight(row.weight_kg) });
  if (row.height_cm !== null)
    fields.push({ label: 'Height', value: formatHeight(row.height_cm) });
  if (row.body_fat_percent !== null)
    fields.push({
      label: 'Body Fat',
      value: formatPercentDecimal(row.body_fat_percent),
    });
  if (row.muscle_mass_kg !== null)
    fields.push({
      label: 'Muscle Mass',
      value: formatWeight(row.muscle_mass_kg),
    });
  if (row.bmi !== null)
    fields.push({ label: 'BMI', value: formatBmi(row.bmi) });
  if (row.resting_heart_rate_bpm !== null)
    fields.push({
      label: 'Resting HR',
      value: `${row.resting_heart_rate_bpm} bpm`,
    });
  if (row.avg_hrv_sdnn_ms !== null)
    fields.push({
      label: 'HRV',
      value: `${Math.round(row.avg_hrv_sdnn_ms)} ms`,
    });
  if (row.body_temperature_celsius !== null)
    fields.push({
      label: 'Body Temp',
      value: formatTemperature(row.body_temperature_celsius),
    });
  if (row.skin_temperature_celsius !== null)
    fields.push({
      label: 'Skin Temp',
      value: formatTemperature(row.skin_temperature_celsius),
    });
  if (row.blood_pressure)
    fields.push({
      label: 'Blood Pressure',
      value: formatBloodPressure(row.blood_pressure),
    });
  return fields;
}

// ============================================================================
// Body Day Row (expandable, mirrors ActivityDayRow)
// ============================================================================

function BodyDayRow({ summary }: { summary: BodyDailySummary }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const detailFields = useMemo(() => getDetailFields(summary), [summary]);
  const hasDetails = detailFields.length > 0;

  return (
    <div className="border border-zinc-800 rounded-lg overflow-hidden bg-zinc-900/30 hover:bg-zinc-900/50 transition-colors">
      <button
        onClick={() => hasDetails && setIsExpanded(!isExpanded)}
        className="w-full px-4 py-3 flex items-center text-left"
        disabled={!hasDetails}
      >
        <div className="w-28 flex-shrink-0">
          <p className="text-sm font-medium text-white">
            {format(new Date(summary.date), 'EEE, MMM d')}
          </p>
          <p className="text-xs text-zinc-500">
            {format(new Date(summary.date), 'yyyy')}
          </p>
          {summary.source?.provider && (
            <SourceBadge provider={summary.source.provider} className="mt-1" />
          )}
        </div>

        <div className="flex-1 flex items-center justify-around">
          <div className="flex items-center gap-2">
            <Scale className="h-4 w-4 text-blue-400" />
            <div>
              <p className="text-sm font-medium text-white">
                {formatWeight(summary.weight_kg)}
              </p>
              <p className="text-xs text-zinc-500">Weight</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-red-400" />
            <div>
              <p className="text-sm font-medium text-white">
                {formatBloodPressure(summary.blood_pressure)}
              </p>
              <p className="text-xs text-zinc-500">BP</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Heart className="h-4 w-4 text-rose-400" />
            <div>
              <p className="text-sm font-medium text-white">
                {summary.resting_heart_rate_bpm
                  ? `${summary.resting_heart_rate_bpm} bpm`
                  : '-'}
              </p>
              <p className="text-xs text-zinc-500">Resting HR</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Thermometer className="h-4 w-4 text-amber-400" />
            <div>
              <p className="text-sm font-medium text-white">
                {formatTemperature(summary.body_temperature_celsius)}
              </p>
              <p className="text-xs text-zinc-500">Temp</p>
            </div>
          </div>
        </div>

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

      {isExpanded && detailFields.length > 0 && (
        <div className="px-4 pb-4 pt-2 border-t border-zinc-800">
          <div className="flex gap-6">
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
            <div className="w-px bg-zinc-800" />
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

// ============================================================================
// Loading skeletons
// ============================================================================

function SummarySkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        {[1, 2, 3, 4, 5].map((i) => (
          <div
            key={i}
            className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30"
          >
            <div className="h-5 w-5 bg-zinc-800 rounded animate-pulse mb-3" />
            <div className="h-7 w-20 bg-zinc-800 rounded animate-pulse mb-1" />
            <div className="h-4 w-16 bg-zinc-800/50 rounded animate-pulse" />
          </div>
        ))}
      </div>
    </div>
  );
}

function DaysSkeleton() {
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

// ============================================================================
// Main component
// ============================================================================

export function BodySection({
  userId,
  dateRange,
  onDateRangeChange,
}: BodySectionProps) {
  const [selectedMetric, setSelectedMetric] = useState<BodyMetricKey>('weight');

  // Snapshot stats for the top metric cards (latest values / period averages)
  const { data: bodySummary, isLoading: snapshotLoading } = useBodySummary(
    userId,
    { average_period: 7 }
  );

  // Daily rollups for the chart (date-range filtered)
  const { startDate, endDate } = useDateRange(dateRange);
  const { data: chartDailyData, isLoading: chartLoading } =
    useBodySummariesDaily(userId, {
      start_date: startDate,
      end_date: endDate,
      limit: 400,
      sort_order: 'asc',
    });

  // Paginated Body Days (all-time, newest first)
  const pagination = useCursorPagination();
  const allTimeRange = useAllTimeRange();
  const {
    data: daysData,
    isLoading: daysLoading,
    isFetching,
  } = useBodySummariesDaily(userId, {
    ...allTimeRange,
    limit: DAYS_PER_PAGE,
    cursor: pagination.currentCursor ?? undefined,
    sort_order: 'desc',
  });

  const nextCursor = daysData?.pagination?.next_cursor ?? null;
  const hasNextPage = daysData?.pagination?.has_more ?? false;
  const handleNextPage = () => pagination.goToNextPage(nextCursor);
  const handlePrevPage = pagination.goToPrevPage;

  const displayedDays = useMemo(() => daysData?.data ?? [], [daysData]);
  const hasDays = displayedDays.length > 0;

  const currentMetric =
    METRIC_BY_KEY[selectedMetric] ?? METRIC_BY_KEY['weight'];

  // Chart data — sorted ascending (oldest → newest) for left-to-right rendering.
  // We emit a uniform shape so Recharts can type-check the data array regardless
  // of which metric is selected.
  type ChartPoint = {
    date: string;
    value: number;
    systolic: number;
    diastolic: number;
  };
  const chartData = useMemo<ChartPoint[]>(() => {
    const rows = chartDailyData?.data ?? [];
    if (rows.length === 0) return [];

    return [...rows]
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .map((row) => {
        const label = format(new Date(row.date), 'MMM d');
        if (currentMetric.key === 'bloodPressure') {
          const bp = row.blood_pressure;
          return {
            date: label,
            value: 0,
            systolic: bp?.avg_systolic_mmhg ?? 0,
            diastolic: bp?.avg_diastolic_mmhg ?? 0,
          };
        }
        const v = currentMetric.getChartValue(row);
        return {
          date: label,
          value: typeof v === 'number' && v !== null ? v : 0,
          systolic: 0,
          diastolic: 0,
        };
      })
      .filter((point) => {
        if (currentMetric.key === 'bloodPressure') {
          return point.systolic > 0 || point.diastolic > 0;
        }
        return point.value > 0;
      });
  }, [chartDailyData, currentMetric]);

  const bmiCategory = getBmiCategory(bodySummary?.slow_changing?.bmi);

  const renderMetricCard = (key: BodyMetricKey) => {
    const metric = METRIC_BY_KEY[key];
    const value = metric.getCardValue(bodySummary);
    const sublabel = metric.getCardSublabel?.(bodySummary);
    // Inject BMI category as a contextual sublabel
    const effectiveSublabel =
      key === 'bmi' && bmiCategory.label ? bmiCategory.label : sublabel;
    const sublabelColor = key === 'bmi' ? bmiCategory.color : undefined;
    return (
      <MetricCard
        key={metric.key}
        icon={metric.icon}
        iconColor={metric.color}
        iconBgColor={metric.bgColor}
        value={value}
        label={metric.label}
        sublabel={effectiveSublabel}
        sublabelColor={sublabelColor}
        isClickable
        isSelected={selectedMetric === metric.key}
        glowColor={metric.glowColor}
        onClick={() => setSelectedMetric(metric.key)}
      />
    );
  };

  return (
    <div className="space-y-6">
      {/* Summary + chart card */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
        <SectionHeader
          title="Body Metrics"
          dateRange={dateRange}
          onDateRangeChange={onDateRangeChange}
        />

        <div className="p-6">
          {snapshotLoading ? (
            <SummarySkeleton />
          ) : !bodySummary ? (
            <p className="text-sm text-zinc-500 text-center py-4">
              No body data in this period
            </p>
          ) : (
            <div className="space-y-6">
              {/* Body Composition */}
              <div>
                <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wider mb-4">
                  Body Composition
                </h4>
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
                  {BODY_COMPOSITION_KEYS.map(renderMetricCard)}
                </div>
              </div>

              {/* Vitals */}
              <div>
                <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wider mb-4">
                  Vitals (7-day avg)
                </h4>
                <div className="grid grid-cols-2 gap-4">
                  {BODY_VITALS_KEYS.map(renderMetricCard)}
                </div>
              </div>

              {/* Recent Readings */}
              <div>
                <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wider mb-4">
                  Recent Readings
                </h4>
                <div className="grid grid-cols-2 gap-4">
                  {BODY_RECENT_READING_KEYS.map(renderMetricCard)}
                </div>
              </div>

              {/* Chart */}
              <div className="pt-4 border-t border-zinc-800">
                <h4 className="text-sm font-medium text-white mb-4">
                  Daily {currentMetric.shortLabel}
                  {currentMetric.unit ? (
                    <span className="text-zinc-500 ml-2">
                      ({currentMetric.unit})
                    </span>
                  ) : null}
                </h4>
                {chartLoading ? (
                  <div className="h-[200px] w-full bg-zinc-900/50 rounded animate-pulse" />
                ) : chartData.length < 2 ? (
                  <p className="text-sm text-zinc-500 text-center py-8">
                    Not enough data to plot{' '}
                    {currentMetric.shortLabel.toLowerCase()} in this range
                  </p>
                ) : currentMetric.key === 'bloodPressure' ? (
                  <ChartContainer
                    config={{
                      systolic: {
                        label: 'Systolic',
                        color: 'hsl(0 84% 60%)',
                      },
                      diastolic: {
                        label: 'Diastolic',
                        color: 'hsl(217 91% 60%)',
                      },
                    }}
                    className="h-[220px] w-full"
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
                        tickFormatter={currentMetric.formatChartTick}
                      />
                      <ChartTooltip
                        cursor={{ fill: 'rgba(255, 255, 255, 0.05)' }}
                        content={<ChartTooltipContent />}
                      />
                      <Legend />
                      <Bar
                        dataKey="systolic"
                        fill="var(--color-systolic)"
                        radius={[4, 4, 0, 0]}
                      />
                      <Bar
                        dataKey="diastolic"
                        fill="var(--color-diastolic)"
                        radius={[4, 4, 0, 0]}
                      />
                    </BarChart>
                  </ChartContainer>
                ) : (
                  <ChartContainer
                    config={{
                      value: {
                        label: currentMetric.shortLabel,
                        color: currentMetric.chartColor,
                      },
                    }}
                    className="h-[220px] w-full"
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
                        tickFormatter={currentMetric.formatChartTick}
                        domain={['auto', 'auto']}
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
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Body Days */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
        <SectionHeader
          title="Body Days"
          rightContent={
            !daysLoading && hasDays ? (
              <span className="text-xs text-zinc-500">
                Page {pagination.currentPage}
              </span>
            ) : undefined
          }
        />
        <div className="p-6">
          {daysLoading ? (
            <DaysSkeleton />
          ) : !hasDays ? (
            <p className="text-sm text-zinc-500 text-center py-8">
              No body data available
            </p>
          ) : (
            <div className="space-y-4">
              <div className="space-y-3">
                {displayedDays.map((row) => (
                  <BodyDayRow key={row.date} summary={row} />
                ))}
              </div>
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

// Re-export helpers consumed elsewhere via the module if any
export { formatLastUpdated, formatHeartRate, formatHrv };

import { useMemo } from 'react';
import { format } from 'date-fns';
import { CartesianGrid, Line, LineChart, XAxis, YAxis } from 'recharts';
import {
  Scale,
  Percent,
  Calculator,
  Dumbbell,
  Heart,
  Activity,
  Ruler,
  Thermometer,
} from 'lucide-react';
import { useBodySummaries } from '@/hooks/api/use-health';
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart';
import type { BodySummary } from '@/lib/api/types';

const weightChartConfig = {
  weight: {
    label: 'Weight (kg)',
    color: '#3b82f6',
  },
} satisfies ChartConfig;

interface BodySectionProps {
  userId: string;
}

function formatWeight(kg: number | null): string {
  if (kg === null) return '-';
  return `${kg.toFixed(1)} kg`;
}

function formatHeight(cm: number | null): string {
  if (cm === null) return '-';
  return `${Math.round(cm)} cm`;
}

function formatPercent(value: number | null): string {
  if (value === null) return '-';
  return `${value.toFixed(1)}%`;
}

function formatBmi(bmi: number | null): string {
  if (bmi === null) return '-';
  return bmi.toFixed(1);
}

function formatTemperature(celsius: number | null): string {
  if (celsius === null) return '-';
  return `${celsius.toFixed(1)}°C`;
}

function getBmiCategory(bmi: number | null): { label: string; color: string } {
  if (bmi === null) return { label: '', color: 'text-zinc-500' };
  if (bmi < 18.5) return { label: 'Underweight', color: 'text-sky-400' };
  if (bmi < 25) return { label: 'Normal', color: 'text-emerald-400' };
  if (bmi < 30) return { label: 'Overweight', color: 'text-amber-400' };
  return { label: 'Obese', color: 'text-rose-400' };
}

// Loading skeleton
function BodySectionSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
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
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30"
          >
            <div className="h-5 w-5 bg-zinc-800 rounded animate-pulse mb-3" />
            <div className="h-7 w-16 bg-zinc-800 rounded animate-pulse mb-1" />
            <div className="h-4 w-20 bg-zinc-800/50 rounded animate-pulse" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function BodySection({ userId }: BodySectionProps) {
  // Fetch last 30 days to ensure we get latest data
  const { startDate, endDate } = useMemo(() => {
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - 30);
    return {
      startDate: start.toISOString(),
      endDate: end.toISOString(),
    };
  }, []);

  const { data: bodySummaries, isLoading } = useBodySummaries(userId, {
    start_date: startDate,
    end_date: endDate,
    limit: 30,
  });

  // Get the most recent summary (which contains latest body composition + 7-day vitals)
  const latestSummary = useMemo(() => {
    const summaries = bodySummaries?.data || [];
    if (summaries.length === 0) return null;

    // Sort by date descending and get the first one with data
    const sorted = [...summaries].sort(
      (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()
    );

    // Find the most recent summary that has at least some data
    for (const s of sorted) {
      if (
        s.weight_kg !== null ||
        s.resting_heart_rate_bpm !== null ||
        s.avg_hrv_sdnn_ms !== null
      ) {
        return s;
      }
    }
    return sorted[0] || null;
  }, [bodySummaries]);

  // For body composition, find the latest non-null value for each metric
  // (they might come from different days)
  const bodyComposition = useMemo(() => {
    const summaries = bodySummaries?.data || [];
    if (summaries.length === 0) return null;

    const sorted = [...summaries].sort(
      (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()
    );

    const findLatest = <T,>(getter: (s: BodySummary) => T | null): T | null => {
      for (const s of sorted) {
        const val = getter(s);
        if (val !== null) return val;
      }
      return null;
    };

    return {
      weight: findLatest((s) => s.weight_kg),
      height: findLatest((s) => s.height_cm),
      bodyFat: findLatest((s) => s.body_fat_percent),
      muscleMass: findLatest((s) => s.muscle_mass_kg),
      bmi: findLatest((s) => s.bmi),
    };
  }, [bodySummaries]);

  const hasData = latestSummary !== null;
  const bmiCategory = getBmiCategory(bodyComposition?.bmi ?? null);

  // Prepare weight trend chart data
  const weightChartData = useMemo(() => {
    const summaries = bodySummaries?.data || [];
    const withWeight = summaries.filter((s) => s.weight_kg != null);
    if (withWeight.length === 0) return [];

    return [...withWeight]
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .map((s) => ({
        date: format(new Date(s.date), 'MMM d'),
        weight: s.weight_kg,
      }));
  }, [bodySummaries]);

  return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
      <div className="px-6 py-4 border-b border-zinc-800 flex items-center justify-between">
        <h3 className="text-sm font-medium text-white">Body Metrics</h3>
        <Scale className="h-4 w-4 text-zinc-500" />
      </div>

      <div className="p-6">
        {isLoading ? (
          <BodySectionSkeleton />
        ) : !hasData ? (
          <p className="text-sm text-zinc-500 text-center py-8">
            No body metrics available yet
          </p>
        ) : (
          <div className="space-y-6">
            {/* Body Composition - Current Values */}
            <div>
              <h4 className="text-xs font-medium text-zinc-400 mb-4 uppercase tracking-wider">
                Current Body Composition
              </h4>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
                {/* Weight */}
                <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 bg-blue-500/10 rounded-lg">
                      <Scale className="h-5 w-5 text-blue-400" />
                    </div>
                  </div>
                  <p className="text-2xl font-semibold text-white">
                    {formatWeight(bodyComposition?.weight ?? null)}
                  </p>
                  <p className="text-xs text-zinc-500 mt-1">Weight</p>
                </div>

                {/* Height */}
                <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 bg-cyan-500/10 rounded-lg">
                      <Ruler className="h-5 w-5 text-cyan-400" />
                    </div>
                  </div>
                  <p className="text-2xl font-semibold text-white">
                    {formatHeight(bodyComposition?.height ?? null)}
                  </p>
                  <p className="text-xs text-zinc-500 mt-1">Height</p>
                </div>

                {/* Body Fat */}
                <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 bg-orange-500/10 rounded-lg">
                      <Percent className="h-5 w-5 text-orange-400" />
                    </div>
                  </div>
                  <p className="text-2xl font-semibold text-white">
                    {formatPercent(bodyComposition?.bodyFat ?? null)}
                  </p>
                  <p className="text-xs text-zinc-500 mt-1">Body Fat</p>
                </div>

                {/* Muscle Mass */}
                <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 bg-emerald-500/10 rounded-lg">
                      <Dumbbell className="h-5 w-5 text-emerald-400" />
                    </div>
                  </div>
                  <p className="text-2xl font-semibold text-white">
                    {formatWeight(bodyComposition?.muscleMass ?? null)}
                  </p>
                  <p className="text-xs text-zinc-500 mt-1">Muscle Mass</p>
                </div>

                {/* BMI */}
                <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 bg-purple-500/10 rounded-lg">
                      <Calculator className="h-5 w-5 text-purple-400" />
                    </div>
                  </div>
                  <p className="text-2xl font-semibold text-white">
                    {formatBmi(bodyComposition?.bmi ?? null)}
                  </p>
                  <p className="text-xs text-zinc-500 mt-1">
                    BMI{' '}
                    {bmiCategory.label && (
                      <span className={bmiCategory.color}>
                        ({bmiCategory.label})
                      </span>
                    )}
                  </p>
                </div>
              </div>
            </div>

            {/* Vitals - 7-Day Averages */}
            <div>
              <h4 className="text-xs font-medium text-zinc-400 mb-4 uppercase tracking-wider">
                7-Day Vitals Average
              </h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {/* Resting Heart Rate */}
                <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 bg-rose-500/10 rounded-lg">
                      <Heart className="h-5 w-5 text-rose-400" />
                    </div>
                  </div>
                  <p className="text-2xl font-semibold text-white">
                    {latestSummary?.resting_heart_rate_bpm != null
                      ? `${latestSummary.resting_heart_rate_bpm}`
                      : '-'}
                  </p>
                  <p className="text-xs text-zinc-500 mt-1">Resting HR (bpm)</p>
                </div>

                {/* HRV */}
                <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 bg-indigo-500/10 rounded-lg">
                      <Activity className="h-5 w-5 text-indigo-400" />
                    </div>
                  </div>
                  <p className="text-2xl font-semibold text-white">
                    {latestSummary?.avg_hrv_sdnn_ms != null
                      ? `${Math.round(latestSummary.avg_hrv_sdnn_ms)}`
                      : '-'}
                  </p>
                  <p className="text-xs text-zinc-500 mt-1">HRV (ms)</p>
                </div>

                {/* Blood Pressure */}
                <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 bg-red-500/10 rounded-lg">
                      <Activity className="h-5 w-5 text-red-400" />
                    </div>
                  </div>
                  <p className="text-2xl font-semibold text-white">
                    {latestSummary?.blood_pressure?.avg_systolic_mmhg != null &&
                    latestSummary?.blood_pressure?.avg_diastolic_mmhg != null
                      ? `${latestSummary.blood_pressure.avg_systolic_mmhg}/${latestSummary.blood_pressure.avg_diastolic_mmhg}`
                      : '-'}
                  </p>
                  <p className="text-xs text-zinc-500 mt-1">
                    Blood Pressure (mmHg)
                  </p>
                </div>

                {/* Temperature */}
                <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 bg-amber-500/10 rounded-lg">
                      <Thermometer className="h-5 w-5 text-amber-400" />
                    </div>
                  </div>
                  <p className="text-2xl font-semibold text-white">
                    {formatTemperature(
                      latestSummary?.basal_body_temperature_celsius ?? null
                    )}
                  </p>
                  <p className="text-xs text-zinc-500 mt-1">Body Temp</p>
                </div>
              </div>
            </div>

            {/* Weight Trend Chart */}
            {weightChartData.length > 1 && (
              <div className="pt-4 border-t border-zinc-800">
                <h4 className="text-xs font-medium text-zinc-400 mb-4 uppercase tracking-wider">
                  Weight Trend
                </h4>
                <ChartContainer
                  config={weightChartConfig}
                  className="h-[200px] w-full"
                >
                  <LineChart
                    accessibilityLayer
                    data={weightChartData}
                    margin={{ left: 12, right: 12 }}
                  >
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
                      domain={['dataMin - 1', 'dataMax + 1']}
                      tickFormatter={(value) => `${value}kg`}
                    />
                    <ChartTooltip
                      cursor={false}
                      content={<ChartTooltipContent />}
                    />
                    <Line
                      dataKey="weight"
                      type="monotone"
                      stroke="var(--color-weight)"
                      strokeWidth={2}
                      dot={{ fill: 'var(--color-weight)', r: 3 }}
                      activeDot={{ r: 5 }}
                    />
                  </LineChart>
                </ChartContainer>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

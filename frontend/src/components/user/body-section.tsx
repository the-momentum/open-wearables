import { useState } from 'react';
import {
  Scale,
  Percent,
  Calculator,
  Dumbbell,
  Heart,
  Activity,
  Ruler,
  Thermometer,
  type LucideIcon,
} from 'lucide-react';
import { useBodySummary } from '@/hooks/api/use-health';
import { SourceBadge } from '@/components/common/source-badge';
import {
  formatWeight,
  formatHeight,
  formatPercentDecimal,
  formatBmi,
  formatTemperature,
} from '@/lib/utils/format';
import {
  getBmiCategory,
  formatLastUpdated,
  formatAveragePeriod,
  formatBloodPressure,
  formatHeartRate,
  formatHrv,
} from '@/lib/utils/body';

interface BodySectionProps {
  userId: string;
}

// ============================================================================
// Metric Card Component - Reusable card for displaying a single metric
// ============================================================================

interface MetricCardProps {
  icon: LucideIcon;
  iconColor: string;
  iconBgColor: string;
  value: string;
  label: string;
  sublabel?: string;
  sublabelColor?: string;
}

function MetricCard({
  icon: Icon,
  iconColor,
  iconBgColor,
  value,
  label,
  sublabel,
  sublabelColor,
}: MetricCardProps) {
  return (
    <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
      <div className="flex items-center gap-3 mb-3">
        <div className={`p-2 ${iconBgColor} rounded-lg`}>
          <Icon className={`h-5 w-5 ${iconColor}`} />
        </div>
      </div>
      <p className="text-2xl font-semibold text-white">{value}</p>
      <p className="text-xs text-zinc-500 mt-1">
        {label}
        {sublabel && (
          <span className={`ml-1 ${sublabelColor ?? 'text-zinc-600'}`}>
            ({sublabel})
          </span>
        )}
      </p>
    </div>
  );
}

// ============================================================================
// Period Toggle Component
// ============================================================================

interface PeriodToggleProps {
  value: 1 | 7;
  onChange: (value: 1 | 7) => void;
}

function PeriodToggle({ value, onChange }: PeriodToggleProps) {
  const getButtonClass = (period: 1 | 7) =>
    `px-2 py-1 text-xs rounded ${
      value === period
        ? 'bg-zinc-700 text-white'
        : 'text-zinc-500 hover:text-zinc-300'
    }`;

  return (
    <div className="flex gap-1">
      <button onClick={() => onChange(1)} className={getButtonClass(1)}>
        Today
      </button>
      <button onClick={() => onChange(7)} className={getButtonClass(7)}>
        7 Days
      </button>
    </div>
  );
}

// ============================================================================
// Loading Skeleton
// ============================================================================

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

// ============================================================================
// Main Component
// ============================================================================

export function BodySection({ userId }: BodySectionProps) {
  const [averagePeriod, setAveragePeriod] = useState<1 | 7>(7);

  const { data: bodySummary, isLoading } = useBodySummary(userId, {
    average_period: averagePeriod,
    latest_window_hours: 4,
  });

  // Derived data
  const slowChangingData = bodySummary?.slow_changing;
  const averagedData = bodySummary?.averaged;
  const latestData = bodySummary?.latest;
  const bmiCategory = getBmiCategory(slowChangingData?.bmi);

  return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
      <div className="px-6 py-4 border-b border-zinc-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-medium text-white">Body Metrics</h3>
          {bodySummary?.source?.provider && (
            <SourceBadge provider={bodySummary.source.provider} />
          )}
        </div>
        <Scale className="h-4 w-4 text-zinc-500" />
      </div>

      <div className="p-6">
        {isLoading ? (
          <BodySectionSkeleton />
        ) : (
          <div className="space-y-6">
            {/* Slow-Changing - Body Composition */}
            <div>
              <div className="mb-4">
                <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wider">
                  Body Composition
                </h4>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
                <MetricCard
                  icon={Scale}
                  iconColor="text-blue-400"
                  iconBgColor="bg-blue-500/10"
                  value={formatWeight(slowChangingData?.weight_kg ?? null)}
                  label="Weight"
                />
                <MetricCard
                  icon={Ruler}
                  iconColor="text-cyan-400"
                  iconBgColor="bg-cyan-500/10"
                  value={formatHeight(slowChangingData?.height_cm ?? null)}
                  label="Height"
                />
                <MetricCard
                  icon={Percent}
                  iconColor="text-orange-400"
                  iconBgColor="bg-orange-500/10"
                  value={formatPercentDecimal(
                    slowChangingData?.body_fat_percent ?? null
                  )}
                  label="Body Fat"
                />
                <MetricCard
                  icon={Dumbbell}
                  iconColor="text-emerald-400"
                  iconBgColor="bg-emerald-500/10"
                  value={formatWeight(slowChangingData?.muscle_mass_kg ?? null)}
                  label="Muscle Mass"
                />
                <MetricCard
                  icon={Calculator}
                  iconColor="text-purple-400"
                  iconBgColor="bg-purple-500/10"
                  value={formatBmi(slowChangingData?.bmi ?? null)}
                  label="BMI"
                  sublabel={bmiCategory.label || undefined}
                  sublabelColor={bmiCategory.color}
                />
              </div>
            </div>

            {/* Averaged - Vitals */}
            <div>
              <div className="flex items-center justify-between mb-4">
                <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wider">
                  Vitals ({formatAveragePeriod(averagePeriod)})
                </h4>
                <PeriodToggle
                  value={averagePeriod}
                  onChange={setAveragePeriod}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <MetricCard
                  icon={Heart}
                  iconColor="text-rose-400"
                  iconBgColor="bg-rose-500/10"
                  value={formatHeartRate(averagedData?.resting_heart_rate_bpm)}
                  label="Resting HR (bpm)"
                />
                <MetricCard
                  icon={Activity}
                  iconColor="text-indigo-400"
                  iconBgColor="bg-indigo-500/10"
                  value={formatHrv(averagedData?.avg_hrv_sdnn_ms)}
                  label="HRV (ms)"
                />
              </div>
            </div>

            {/* Latest - Recent Readings */}
            <div>
              <div className="flex items-center justify-between mb-4">
                <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wider">
                  Recent Readings
                </h4>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <MetricCard
                  icon={Thermometer}
                  iconColor="text-amber-400"
                  iconBgColor="bg-amber-500/10"
                  value={formatTemperature(
                    latestData?.body_temperature_celsius ?? null
                  )}
                  label="Body Temp"
                  sublabel={
                    latestData?.temperature_measured_at
                      ? formatLastUpdated(latestData.temperature_measured_at)
                      : undefined
                  }
                />
                <MetricCard
                  icon={Activity}
                  iconColor="text-red-400"
                  iconBgColor="bg-red-500/10"
                  value={formatBloodPressure(latestData?.blood_pressure)}
                  label="Blood Pressure"
                  sublabel={
                    latestData?.blood_pressure_measured_at
                      ? formatLastUpdated(latestData.blood_pressure_measured_at)
                      : undefined
                  }
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

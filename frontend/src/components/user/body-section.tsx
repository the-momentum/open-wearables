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
    <div className="p-4 border border-border/60 rounded-lg bg-card/30">
      <div className="flex items-center gap-3 mb-3">
        <div className={`p-2 ${iconBgColor} rounded-lg`}>
          <Icon className={`h-5 w-5 ${iconColor}`} />
        </div>
      </div>
      <p className="text-2xl font-semibold text-foreground">{value}</p>
      <p className="text-xs text-muted-foreground mt-1">
        {label}
        {sublabel && (
          <span
            className={`ml-1 ${sublabelColor ?? 'text-muted-foreground/70'}`}
          >
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
        ? 'bg-muted-foreground/40 text-foreground'
        : 'text-muted-foreground hover:text-foreground/90'
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
            className="p-4 border border-border/60 rounded-lg bg-card/30"
          >
            <div className="h-5 w-5 bg-muted rounded animate-pulse mb-3" />
            <div className="h-7 w-20 bg-muted rounded animate-pulse mb-1" />
            <div className="h-4 w-16 bg-muted/50 rounded animate-pulse" />
          </div>
        ))}
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="p-4 border border-border/60 rounded-lg bg-card/30"
          >
            <div className="h-5 w-5 bg-muted rounded animate-pulse mb-3" />
            <div className="h-7 w-16 bg-muted rounded animate-pulse mb-1" />
            <div className="h-4 w-20 bg-muted/50 rounded animate-pulse" />
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

  const hrvValue =
    averagedData?.avg_hrv_sdnn_ms ?? averagedData?.avg_hrv_rmssd_ms ?? null;
  const hrvLabel =
    averagedData?.avg_hrv_sdnn_ms != null
      ? 'HRV SDNN (ms)'
      : averagedData?.avg_hrv_rmssd_ms != null
        ? 'HRV RMSSD (ms)'
        : 'HRV (ms)';

  return (
    <div className="rounded-2xl border border-border/60 bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-xl overflow-hidden">
      <div className="px-6 py-4 border-b border-border/60 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-medium text-foreground">Body Metrics</h3>
          {bodySummary?.source?.provider && (
            <SourceBadge provider={bodySummary.source.provider} />
          )}
        </div>
        <Scale className="h-4 w-4 text-muted-foreground" />
      </div>

      <div className="p-6">
        {isLoading ? (
          <BodySectionSkeleton />
        ) : (
          <div className="space-y-6">
            {/* Slow-Changing - Body Composition */}
            <div>
              <div className="mb-4">
                <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
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
                  iconColor="text-[hsl(var(--success-muted))]"
                  iconBgColor="bg-[hsl(var(--success-muted)/0.1)]"
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
                <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
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
                  value={formatHrv(hrvValue)}
                  label={hrvLabel}
                />
              </div>
            </div>

            {/* Latest - Recent Readings */}
            <div>
              <div className="flex items-center justify-between mb-4">
                <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Recent Readings
                </h4>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <MetricCard
                  icon={Thermometer}
                  iconColor="text-[hsl(var(--warning-muted))]"
                  iconBgColor="bg-[hsl(var(--warning-muted)/0.1)]"
                  value={formatTemperature(
                    latestData?.body_temperature_celsius ?? null
                  )}
                  label="Body Temp"
                  sublabel={
                    latestData?.body_temperature_measured_at
                      ? formatLastUpdated(
                          latestData.body_temperature_measured_at
                        )
                      : undefined
                  }
                />
                <MetricCard
                  icon={Activity}
                  iconColor="text-[hsl(var(--destructive-muted))]"
                  iconBgColor="bg-[hsl(var(--destructive-muted)/0.1)]"
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

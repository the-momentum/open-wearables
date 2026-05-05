import { BarChart3, Dumbbell } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface SeriesTypeMetric {
  series_type: string;
  count: number;
}

export interface WorkoutTypeMetric {
  workout_type: string | null;
  count: number;
}

export interface DataMetricsSectionProps {
  topSeriesTypes: SeriesTypeMetric[];
  topWorkoutTypes: WorkoutTypeMetric[];
  className?: string;
}

interface MetricCardProps {
  index: number;
  label: string;
  count: number;
  max: number;
}

function MetricCard({ index, label, count, max }: MetricCardProps) {
  const pct = max > 0 ? Math.round((count / max) * 100) : 0;

  return (
    <div className="group relative flex flex-col overflow-hidden rounded-xl border border-border/60 bg-card/40 transition-all duration-200 hover:border-border/80 hover:bg-card/60">
      {/* Rank badge */}
      <span className="absolute right-2.5 top-2.5 font-mono text-[10px] tabular-nums text-muted-foreground/40">
        #{index + 1}
      </span>
      <div className="flex-1 space-y-1 p-4">
        <p className="text-xl font-bold leading-none tabular-nums text-foreground">
          {count.toLocaleString()}
        </p>
        <p
          className="truncate pr-5 text-xs capitalize text-muted-foreground"
          title={label}
        >
          {label}
        </p>
      </div>
      {/* Progress bar — relative scale, #1 = 100% */}
      <div className="h-1 w-full bg-muted/40">
        <div
          className="h-full bg-[hsl(var(--primary-muted))] transition-[width] duration-700 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function SectionHeader({
  icon: Icon,
  title,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
}) {
  return (
    <div className="mb-4 flex items-center gap-2">
      <div className="flex h-6 w-6 items-center justify-center rounded-md border border-border/60 bg-muted/40">
        <Icon className="h-3.5 w-3.5 text-muted-foreground" />
      </div>
      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </h3>
    </div>
  );
}

export function DataMetricsSection({
  topSeriesTypes,
  topWorkoutTypes,
  className,
}: DataMetricsSectionProps) {
  const seriesMax = Math.max(0, ...topSeriesTypes.map((m) => m.count));
  const workoutMax = Math.max(0, ...topWorkoutTypes.map((m) => m.count));

  return (
    <div
      className={cn(
        'relative overflow-hidden rounded-2xl border border-border/60',
        'bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-xl',
        className
      )}
    >
      <div className="flex items-center justify-between border-b border-border/60 px-6 py-4">
        <div>
          <h2 className="text-base font-semibold text-foreground">
            Data Points Metrics
          </h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Breakdown by series type and workout type
          </p>
        </div>
        <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-border/60 bg-muted/40">
          <BarChart3 className="h-4 w-4 text-muted-foreground" />
        </div>
      </div>

      <div className="grid gap-8 p-6 md:grid-cols-2">
        {/* Top Series Types */}
        <section>
          <SectionHeader icon={BarChart3} title="Top Series Types" />
          {topSeriesTypes.length > 0 ? (
            <div className="grid grid-cols-2 gap-3">
              {topSeriesTypes.map((metric, index) => (
                <MetricCard
                  key={metric.series_type}
                  index={index}
                  label={metric.series_type.replace(/_/g, ' ')}
                  count={metric.count}
                  max={seriesMax}
                />
              ))}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">No data available</p>
          )}
        </section>

        {/* Top Workout Types */}
        <section>
          <SectionHeader icon={Dumbbell} title="Top Workout Types" />
          {topWorkoutTypes.length > 0 ? (
            <div className="grid grid-cols-2 gap-3">
              {topWorkoutTypes.map((metric, index) => (
                <MetricCard
                  key={metric.workout_type || 'unknown'}
                  index={index}
                  label={metric.workout_type || 'Unknown'}
                  count={metric.count}
                  max={workoutMax}
                />
              ))}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">No data available</p>
          )}
        </section>
      </div>
    </div>
  );
}

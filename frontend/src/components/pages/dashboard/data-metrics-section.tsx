import { useState } from 'react';
import { BarChart3, Dumbbell, Link2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { getWorkoutStyle } from '@/lib/utils/workout-styles';
import { SourceBadge } from '@/components/common/source-badge';
import type { ConnectionsCoverage } from '@/lib/api/types';

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
  connectionsCoverage: ConnectionsCoverage;
  totalUsers: number;
  className?: string;
}

const RANK_COLORS = [
  'text-[hsl(var(--primary))]',
  'text-[hsl(var(--foreground-muted))]',
  'text-[hsl(var(--foreground-subtle))]',
];

function SeriesCard({
  index,
  label,
  count,
}: {
  index: number;
  label: string;
  count: number;
}) {
  return (
    <div className="flex flex-col gap-2 rounded-xl border border-border/60 bg-card/40 p-4 transition-colors duration-200 hover:bg-card/60">
      <span
        className={cn(
          'font-mono text-[10px] font-semibold',
          RANK_COLORS[index] ?? RANK_COLORS[2]
        )}
      >
        #{index + 1}
      </span>
      <p className="text-2xl font-bold tabular-nums leading-none text-foreground">
        {count.toLocaleString()}
      </p>
      <p
        className="truncate text-xs capitalize text-muted-foreground"
        title={label}
      >
        {label}
      </p>
    </div>
  );
}

function WorkoutCard({
  index,
  type,
  count,
}: {
  index: number;
  type: string | null;
  count: number;
}) {
  const style = getWorkoutStyle(type);
  return (
    <div className="flex flex-col gap-2 rounded-xl border border-border/60 bg-card/40 p-4 transition-colors duration-200 hover:bg-card/60">
      <span
        className={cn(
          'font-mono text-[10px] font-semibold',
          RANK_COLORS[index] ?? RANK_COLORS[2]
        )}
      >
        #{index + 1}
      </span>
      <p className="text-2xl font-bold tabular-nums leading-none text-foreground">
        {count.toLocaleString()}
      </p>
      <p className="truncate text-xs text-muted-foreground" title={style.label}>
        {style.label}
      </p>
    </div>
  );
}

const TABS = [
  { value: 'coverage', label: 'Coverage', icon: Link2 },
  { value: 'series', label: 'Series types', icon: BarChart3 },
  { value: 'workouts', label: 'Workout types', icon: Dumbbell },
] as const;

type Tab = (typeof TABS)[number]['value'];

export function DataMetricsSection({
  topSeriesTypes,
  topWorkoutTypes,
  connectionsCoverage,
  totalUsers,
  className,
}: DataMetricsSectionProps) {
  const [tab, setTab] = useState<Tab>('coverage');
  const tabIndex = TABS.findIndex((t) => t.value === tab);

  const seriesTop6 = topSeriesTypes.slice(0, 6);
  const workoutsTop6 = topWorkoutTypes.slice(0, 6);

  const coveredPct =
    totalUsers > 0
      ? Math.round((connectionsCoverage.users_with_active / totalUsers) * 100)
      : 0;
  const uncoveredPct = 100 - coveredPct;
  const multiPct =
    totalUsers > 0
      ? Math.round(
          (connectionsCoverage.users_with_multi_active / totalUsers) * 100
        )
      : 0;

  return (
    <div
      className={cn(
        'relative overflow-hidden rounded-2xl border border-border/60',
        'bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-xl',
        className
      )}
    >
      <div className="flex items-center gap-3 border-b border-border/60 px-4 py-2">
        <div
          role="tablist"
          aria-label="Data metrics"
          className="relative flex flex-1 rounded-lg bg-foreground/5 p-1"
        >
          <span
            aria-hidden
            className="absolute inset-y-1 rounded-md bg-white shadow-sm transition-transform duration-200 ease-out"
            style={{
              width: `${100 / TABS.length}%`,
              transform: `translateX(${tabIndex * 100}%)`,
            }}
          />
          {TABS.map(({ value, label, icon: Icon }) => {
            const active = tab === value;
            return (
              <button
                key={value}
                type="button"
                role="tab"
                id={`metrics-tab-${value}`}
                aria-selected={active}
                aria-controls={`metrics-panel-${value}`}
                tabIndex={active ? 0 : -1}
                onClick={() => setTab(value)}
                className={cn(
                  'relative z-10 flex flex-1 items-center justify-center gap-1.5 whitespace-nowrap rounded-md px-2 py-1.5 text-sm font-medium transition-colors duration-200',
                  active
                    ? 'text-zinc-900'
                    : 'text-muted-foreground hover:text-foreground/70'
                )}
              >
                <Icon className="h-3.5 w-3.5 shrink-0" />
                {label}
              </button>
            );
          })}
        </div>
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border/60 bg-muted/40">
          <BarChart3 className="h-3.5 w-3.5 text-muted-foreground" />
        </div>
      </div>

      <div className="p-6">
        {tab === 'coverage' && (
          <div
            role="tabpanel"
            id="metrics-panel-coverage"
            aria-labelledby="metrics-tab-coverage"
            className="space-y-5"
          >
            {/* Header */}
            <div className="flex items-baseline justify-between">
              <span className="text-sm font-semibold text-foreground">
                Active connections
              </span>
              <span className="font-mono text-2xl font-bold leading-none text-foreground">
                {coveredPct}
                <span className="ml-0.5 text-sm font-normal text-muted-foreground">
                  %
                </span>
              </span>
            </div>

            {totalUsers === 0 ? (
              <p className="py-4 text-center text-sm text-muted-foreground">
                No users yet
              </p>
            ) : (
              <>
                {/* Main bar: green + red side by side */}
                <div className="pb-3">
                  <div className="relative">
                    <div className="flex h-5 w-full overflow-hidden rounded-lg border border-border/30 bg-muted/20">
                      <div
                        className="h-full transition-[width] duration-700 ease-out"
                        style={{
                          width: `${coveredPct}%`,
                          background:
                            'linear-gradient(to right, hsl(var(--success-muted)), hsl(var(--success-muted)/0.6))',
                        }}
                      />
                      <div
                        className="h-full transition-[width] duration-700 ease-out"
                        style={{
                          width: `${uncoveredPct}%`,
                          background:
                            'linear-gradient(to right, hsl(var(--destructive-muted)/0.8), hsl(var(--destructive-muted)/0.5))',
                        }}
                      />
                    </div>
                    {/* Upward triangle marker at multiPct position */}
                    <div
                      className="absolute top-full mt-1 -translate-x-1/2 transition-[left] duration-700 ease-out"
                      style={{ left: `${multiPct}%` }}
                    >
                      <div className="h-0 w-0 border-l-[7px] border-r-[7px] border-b-[9px] border-l-transparent border-r-transparent border-b-[hsl(var(--primary)/0.8)]" />
                    </div>
                  </div>
                </div>

                {/* Legend */}
                <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                  <span className="flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full bg-[hsl(var(--success-muted))]" />
                    <span className="font-mono font-semibold text-foreground">
                      {connectionsCoverage.users_with_active.toLocaleString()}
                    </span>{' '}
                    connected
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="inline-block h-0 w-0 border-l-[6px] border-r-[6px] border-b-[8px] border-l-transparent border-r-transparent border-b-[hsl(var(--primary)/0.8)]" />
                    <span className="font-mono font-semibold text-foreground">
                      {connectionsCoverage.users_with_multi_active.toLocaleString()}
                    </span>{' '}
                    multiple connections
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full bg-[hsl(var(--destructive-muted))]" />
                    <span className="font-mono font-semibold text-foreground">
                      {(
                        totalUsers - connectionsCoverage.users_with_active
                      ).toLocaleString()}
                    </span>{' '}
                    not connected
                  </span>
                </div>
              </>
            )}

            {/* Top providers */}
            {connectionsCoverage.top_providers.length > 0 && (
              <div className="space-y-2 border-t border-border/50 pt-4">
                <p className="text-sm font-semibold text-foreground">
                  Top providers
                </p>
                <div className="grid grid-cols-3 gap-2">
                  {connectionsCoverage.top_providers.map(
                    ({ provider, count }) => (
                      <div
                        key={provider}
                        className="flex flex-col items-center gap-2 rounded-xl border border-border/60 bg-card/40 px-2 py-3 text-center"
                      >
                        <SourceBadge provider={provider} />
                        <p className="font-mono text-2xl font-bold tabular-nums leading-none text-foreground">
                          {count.toLocaleString()}
                        </p>
                        <p className="text-[10px] leading-none text-muted-foreground">
                          connections
                        </p>
                      </div>
                    )
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {tab === 'series' && (
          <div
            role="tabpanel"
            id="metrics-panel-series"
            aria-labelledby="metrics-tab-series"
          >
            {seriesTop6.length > 0 ? (
              <div className="grid grid-cols-3 gap-3">
                {seriesTop6.map((m, i) => (
                  <SeriesCard
                    key={m.series_type}
                    index={i}
                    label={m.series_type.replace(/_/g, ' ')}
                    count={m.count}
                  />
                ))}
              </div>
            ) : (
              <p className="py-8 text-center text-sm text-muted-foreground">
                No data available
              </p>
            )}
          </div>
        )}

        {tab === 'workouts' && (
          <div
            role="tabpanel"
            id="metrics-panel-workouts"
            aria-labelledby="metrics-tab-workouts"
          >
            {workoutsTop6.length > 0 ? (
              <div className="grid grid-cols-3 gap-3">
                {workoutsTop6.map((m, i) => (
                  <WorkoutCard
                    key={m.workout_type ?? 'unknown'}
                    index={i}
                    type={m.workout_type}
                    count={m.count}
                  />
                ))}
              </div>
            ) : (
              <p className="py-8 text-center text-sm text-muted-foreground">
                No data available
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

import { Database, Dumbbell, Moon, ChevronDown, ChevronUp } from 'lucide-react';
import { useState } from 'react';
import { useUserDataSummary } from '@/hooks/api/use-health';
import { formatNumber } from '@/lib/utils/format';
import type { ProviderDataCount } from '@/lib/api/types';

interface DataSummarySectionProps {
  userId: string;
}

function formatSeriesType(code: string): string {
  return code.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatProvider(provider: string): string {
  return provider.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function StatCard({
  icon: Icon,
  label,
  value,
  iconClass,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: number;
  iconClass?: string;
}) {
  return (
    <div className="relative overflow-hidden rounded-xl border border-border/60 bg-card/40 p-4 transition-colors hover:bg-card/60">
      <div
        className={`mb-3 flex h-9 w-9 items-center justify-center rounded-lg border ${iconClass ?? 'border-border/60 bg-muted/40 text-muted-foreground'}`}
      >
        <Icon className="h-4 w-4" />
      </div>
      <p className="text-2xl font-bold tabular-nums text-foreground">
        {formatNumber(value)}
      </p>
      <p className="mt-0.5 text-xs text-muted-foreground">{label}</p>
    </div>
  );
}

function TypeGrid({
  counts,
  limit,
}: {
  counts: Record<string, number>;
  limit?: number;
}) {
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  const displayed = limit ? entries.slice(0, limit) : entries;
  const max = Math.max(0, ...displayed.map(([, c]) => c));

  if (displayed.length === 0) {
    return <p className="text-sm text-muted-foreground">No data points</p>;
  }

  return (
    <div className="grid grid-cols-2 gap-2">
      {displayed.map(([type, count]) => {
        const pct = max > 0 ? Math.max(5, (count / max) * 100) : 0;
        return (
          <div
            key={type}
            className="flex flex-col overflow-hidden rounded-lg border border-border/60 bg-card/30 transition-colors hover:bg-card/50"
          >
            <div className="flex-1 p-3">
              <p className="text-sm font-semibold tabular-nums text-foreground/90">
                {formatNumber(count)}
              </p>
              <p
                className="mt-0.5 truncate text-[10px] text-muted-foreground"
                title={formatSeriesType(type)}
              >
                {formatSeriesType(type)}
              </p>
            </div>
            {/* Progress bar — relative scale, #1 = 100% */}
            <div className="h-0.5 w-full bg-muted/40">
              <div
                className="h-full bg-[hsl(var(--primary-muted))] transition-[width] duration-700 ease-out"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function ProviderCard({ provider }: { provider: ProviderDataCount }) {
  const [expanded, setExpanded] = useState(false);
  const totalRecords =
    provider.data_points + provider.workout_count + provider.sleep_count;
  const seriesEntries = Object.entries(provider.series_counts);

  return (
    <div className="overflow-hidden rounded-xl border border-border/60 bg-card/40 transition-colors hover:border-border/80">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between px-4 py-3.5 text-left transition-colors hover:bg-card/60"
      >
        <div className="flex items-center gap-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-md border border-border/60 bg-muted/40">
            <span className="text-[10px] font-bold text-foreground/70">
              {formatProvider(provider.provider).charAt(0)}
            </span>
          </div>
          <div>
            <span className="text-sm font-medium text-foreground">
              {formatProvider(provider.provider)}
            </span>
            <span className="ml-2 rounded-full border border-border/60 bg-muted/40 px-1.5 py-0.5 text-[10px] tabular-nums text-muted-foreground">
              {formatNumber(totalRecords)}
            </span>
          </div>
        </div>
        {expanded ? (
          <ChevronUp className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        )}
      </button>

      {expanded && (
        <div className="space-y-4 border-t border-border/60 px-4 py-4">
          <div className="grid grid-cols-3 gap-2">
            {[
              { label: 'Data Points', value: provider.data_points },
              { label: 'Workouts', value: provider.workout_count },
              { label: 'Sleep', value: provider.sleep_count },
            ].map(({ label, value }) => (
              <div
                key={label}
                className="rounded-lg border border-border/60 bg-card/30 p-3 text-center"
              >
                <p className="text-base font-semibold tabular-nums text-foreground/90">
                  {formatNumber(value)}
                </p>
                <p className="mt-0.5 text-[10px] text-muted-foreground">
                  {label}
                </p>
              </div>
            ))}
          </div>

          {seriesEntries.length > 0 && (
            <TypeGrid counts={provider.series_counts} />
          )}
        </div>
      )}
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="h-[72px] rounded-lg border border-border/60 bg-muted/30 animate-pulse"
          />
        ))}
      </div>
      <div className="space-y-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-8 bg-muted/30 rounded animate-pulse" />
        ))}
      </div>
    </div>
  );
}

export function DataSummarySection({ userId }: DataSummarySectionProps) {
  const { data, isLoading } = useUserDataSummary(userId);
  const [showAllTypes, setShowAllTypes] = useState(false);

  const isEmpty =
    data &&
    data.total_data_points === 0 &&
    data.total_workouts === 0 &&
    data.total_sleep_events === 0;

  return (
    <div className="rounded-2xl border border-border/60 bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-xl overflow-hidden">
      <div className="px-6 py-4 border-b border-border/60">
        <h2 className="text-sm font-medium text-foreground">Data Summary</h2>
        <p className="text-xs text-muted-foreground mt-1">
          Overview of all health data collected for this user
        </p>
      </div>
      <div className="p-6">
        {isLoading ? (
          <LoadingSkeleton />
        ) : isEmpty ? (
          <div className="text-center py-8">
            <p className="text-muted-foreground">No data collected yet</p>
          </div>
        ) : data ? (
          <div className="space-y-6">
            {/* Summary stats */}
            <div className="grid grid-cols-3 gap-3">
              <StatCard
                icon={Database}
                label="Data Points"
                value={data.total_data_points}
                iconClass="border-[hsl(var(--primary)/0.3)] bg-[hsl(var(--primary)/0.1)] text-[hsl(var(--primary-muted))]"
              />
              <StatCard
                icon={Dumbbell}
                label="Workouts"
                value={data.total_workouts}
                iconClass="border-[hsl(var(--secondary-muted)/0.3)] bg-[hsl(var(--secondary-muted)/0.1)] text-[hsl(var(--secondary-muted))]"
              />
              <StatCard
                icon={Moon}
                label="Sleep Events"
                value={data.total_sleep_events}
                iconClass="border-[hsl(var(--accent-muted)/0.3)] bg-[hsl(var(--accent-muted)/0.1)] text-[hsl(var(--accent-muted))]"
              />
            </div>

            {/* Series types */}
            {Object.keys(data.series_type_counts).length > 0 && (
              <div>
                <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Series Types
                </h3>
                <TypeGrid
                  counts={data.series_type_counts}
                  limit={showAllTypes ? undefined : 8}
                />
                {Object.keys(data.series_type_counts).length > 8 && (
                  <button
                    type="button"
                    onClick={() => setShowAllTypes(!showAllTypes)}
                    className="mt-3 text-xs text-muted-foreground transition-colors hover:text-foreground/90"
                  >
                    {showAllTypes
                      ? 'Show less'
                      : `Show all ${Object.keys(data.series_type_counts).length} types`}
                  </button>
                )}
              </div>
            )}

            {/* Workout types */}
            {Object.keys(data.workout_type_counts).length > 0 && (
              <div>
                <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Workout Types
                </h3>
                <TypeGrid counts={data.workout_type_counts} />
              </div>
            )}

            {/* Provider breakdown */}
            {data.by_provider.length > 0 && (
              <div>
                <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  By Provider
                </h3>
                <div className="space-y-2">
                  {data.by_provider.map((provider) => (
                    <ProviderCard key={provider.provider} provider={provider} />
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}

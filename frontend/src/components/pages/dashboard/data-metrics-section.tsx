import { BarChart3 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatCompactNumber } from '@/lib/utils/format';
import { SourceBadge } from '@/components/common/source-badge';
import type { ConnectionsCoverage } from '@/lib/api/types';

export interface DataMetricsSectionProps {
  connectionsCoverage: ConnectionsCoverage;
  totalUsers: number;
  className?: string;
}

export function DataMetricsSection({
  connectionsCoverage,
  totalUsers,
  className,
}: DataMetricsSectionProps) {
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
      <div className="flex items-center gap-3 border-b border-border/60 px-4 py-3">
        <span className="flex-1 text-sm font-semibold text-foreground">
          Connection coverage
        </span>
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border/60 bg-muted/40">
          <BarChart3 className="h-3.5 w-3.5 text-muted-foreground" />
        </div>
      </div>

      <div className="p-6">
        <div className="space-y-5">
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
                    {formatCompactNumber(connectionsCoverage.users_with_active)}
                  </span>{' '}
                  connected
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="inline-block h-0 w-0 border-l-[6px] border-r-[6px] border-b-[8px] border-l-transparent border-r-transparent border-b-[hsl(var(--primary)/0.8)]" />
                  <span className="font-mono font-semibold text-foreground">
                    {formatCompactNumber(
                      connectionsCoverage.users_with_multi_active
                    )}
                  </span>{' '}
                  multiple connections
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-[hsl(var(--destructive-muted))]" />
                  <span className="font-mono font-semibold text-foreground">
                    {formatCompactNumber(
                      totalUsers - connectionsCoverage.users_with_active
                    )}
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
                        {formatCompactNumber(count)}
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
      </div>
    </div>
  );
}

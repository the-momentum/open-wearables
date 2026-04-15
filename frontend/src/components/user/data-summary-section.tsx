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
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: number;
}) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-900/30 p-4">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-zinc-800">
        <Icon className="h-4 w-4 text-zinc-400" />
      </div>
      <div>
        <p className="text-xs text-zinc-500">{label}</p>
        <p className="text-lg font-semibold text-white">
          {formatNumber(value)}
        </p>
      </div>
    </div>
  );
}

function SeriesTypeTable({
  counts,
  limit,
}: {
  counts: Record<string, number>;
  limit?: number;
}) {
  const entries = Object.entries(counts);
  const displayed = limit ? entries.slice(0, limit) : entries;

  if (displayed.length === 0) {
    return <p className="text-sm text-zinc-500">No data points</p>;
  }

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-zinc-800 text-left">
          <th className="pb-2 font-medium text-zinc-500">Type</th>
          <th className="pb-2 text-right font-medium text-zinc-500">Count</th>
        </tr>
      </thead>
      <tbody>
        {displayed.map(([type, count]) => (
          <tr key={type} className="border-b border-zinc-800/50">
            <td className="py-1.5 text-zinc-300">{formatSeriesType(type)}</td>
            <td className="py-1.5 text-right tabular-nums text-zinc-400">
              {formatNumber(count)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ProviderCard({ provider }: { provider: ProviderDataCount }) {
  const [expanded, setExpanded] = useState(false);
  const totalRecords =
    provider.data_points + provider.workout_count + provider.sleep_count;
  const seriesEntries = Object.entries(provider.series_counts);

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/30">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-zinc-800/30 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-white">
            {formatProvider(provider.provider)}
          </span>
          <span className="text-xs text-zinc-500">
            {formatNumber(totalRecords)} records
          </span>
        </div>
        {expanded ? (
          <ChevronUp className="h-4 w-4 text-zinc-500" />
        ) : (
          <ChevronDown className="h-4 w-4 text-zinc-500" />
        )}
      </button>

      {expanded && (
        <div className="border-t border-zinc-800 px-4 py-3 space-y-3">
          <div className="grid grid-cols-3 gap-3 text-center">
            <div>
              <p className="text-xs text-zinc-500">Data Points</p>
              <p className="text-sm font-medium text-zinc-300">
                {formatNumber(provider.data_points)}
              </p>
            </div>
            <div>
              <p className="text-xs text-zinc-500">Workouts</p>
              <p className="text-sm font-medium text-zinc-300">
                {formatNumber(provider.workout_count)}
              </p>
            </div>
            <div>
              <p className="text-xs text-zinc-500">Sleep</p>
              <p className="text-sm font-medium text-zinc-300">
                {formatNumber(provider.sleep_count)}
              </p>
            </div>
          </div>

          {seriesEntries.length > 0 && (
            <SeriesTypeTable counts={provider.series_counts} />
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
            className="h-[72px] rounded-lg border border-zinc-800 bg-zinc-800/30 animate-pulse"
          />
        ))}
      </div>
      <div className="space-y-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-8 bg-zinc-800/30 rounded animate-pulse" />
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
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
      <div className="px-6 py-4 border-b border-zinc-800">
        <h2 className="text-sm font-medium text-white">Data Summary</h2>
        <p className="text-xs text-zinc-500 mt-1">
          Overview of all health data collected for this user
        </p>
      </div>
      <div className="p-6">
        {isLoading ? (
          <LoadingSkeleton />
        ) : isEmpty ? (
          <div className="text-center py-8">
            <p className="text-zinc-500">No data collected yet</p>
          </div>
        ) : data ? (
          <div className="space-y-6">
            {/* Summary stats */}
            <div className="grid grid-cols-3 gap-4">
              <StatCard
                icon={Database}
                label="Data Points"
                value={data.total_data_points}
              />
              <StatCard
                icon={Dumbbell}
                label="Workouts"
                value={data.total_workouts}
              />
              <StatCard
                icon={Moon}
                label="Sleep Events"
                value={data.total_sleep_events}
              />
            </div>

            {/* Series types */}
            {Object.keys(data.series_type_counts).length > 0 && (
              <div>
                <h3 className="text-xs font-medium text-zinc-500 mb-2">
                  Series Types
                </h3>
                <SeriesTypeTable
                  counts={data.series_type_counts}
                  limit={showAllTypes ? undefined : 8}
                />
                {Object.keys(data.series_type_counts).length > 8 && (
                  <button
                    type="button"
                    onClick={() => setShowAllTypes(!showAllTypes)}
                    className="mt-2 text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
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
                <h3 className="text-xs font-medium text-zinc-500 mb-2">
                  Workout Types
                </h3>
                <SeriesTypeTable counts={data.workout_type_counts} />
              </div>
            )}

            {/* Provider breakdown */}
            {data.by_provider.length > 0 && (
              <div>
                <h3 className="text-xs font-medium text-zinc-500 mb-2">
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

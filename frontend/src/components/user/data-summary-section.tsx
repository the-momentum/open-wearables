import { useState } from 'react';
import { ChevronDown, ChevronUp, Database } from 'lucide-react';
import { useUserDataStats } from '@/hooks/api/use-users';
import { Button } from '@/components/ui/button';

interface DataSummarySectionProps {
  userId: string;
}

const COLLAPSED_LIMIT = 5;

export function DataSummarySection({ userId }: DataSummarySectionProps) {
  const { data: stats, isLoading } = useUserDataStats(userId);
  const [seriesExpanded, setSeriesExpanded] = useState(false);
  const [eventsExpanded, setEventsExpanded] = useState(false);

  if (isLoading) {
    return (
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-zinc-800">
          <div className="h-4 w-28 bg-zinc-800/50 rounded animate-pulse" />
        </div>
        <div className="p-6 space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="flex justify-between">
              <div className="h-4 w-32 bg-zinc-800/50 rounded animate-pulse" />
              <div className="h-4 w-12 bg-zinc-800/50 rounded animate-pulse" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  const hasData =
    stats && (stats.total_data_points > 0 || stats.event_types.length > 0);

  const visibleSeries = seriesExpanded
    ? stats?.series_types
    : stats?.series_types.slice(0, COLLAPSED_LIMIT);

  const visibleEvents = eventsExpanded
    ? stats?.event_types
    : stats?.event_types.slice(0, COLLAPSED_LIMIT);

  return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
      <div className="px-6 py-4 border-b border-zinc-800">
        <h2 className="text-sm font-medium text-white">Data Summary</h2>
        <p className="text-xs text-zinc-500 mt-1">
          Overview of collected data types and counts
        </p>
      </div>
      <div className="p-6">
        {!hasData ? (
          <div className="text-center py-6">
            <Database className="h-8 w-8 text-zinc-700 mx-auto mb-2" />
            <p className="text-sm text-zinc-500">No data collected yet</p>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Total */}
            <div className="flex items-center justify-between pb-4 border-b border-zinc-800/50">
              <span className="text-sm text-zinc-400">
                Total Time-Series Data Points
              </span>
              <span className="text-lg font-semibold text-white">
                {stats.total_data_points.toLocaleString()}
              </span>
            </div>

            {/* Series Types */}
            {stats.series_types.length > 0 && (
              <div>
                <h3 className="text-xs font-medium text-zinc-400 mb-3">
                  Series Types ({stats.series_types.length})
                </h3>
                <div className="space-y-2">
                  {visibleSeries?.map((metric) => (
                    <div
                      key={metric.series_type}
                      className="flex items-center justify-between"
                    >
                      <span className="text-sm text-zinc-300 capitalize">
                        {metric.series_type.replace(/_/g, ' ')}
                      </span>
                      <span className="text-sm font-medium text-white">
                        {metric.count.toLocaleString()}
                      </span>
                    </div>
                  ))}
                </div>
                {stats.series_types.length > COLLAPSED_LIMIT && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setSeriesExpanded(!seriesExpanded)}
                    className="mt-2 text-xs text-zinc-500 hover:text-zinc-300 px-0"
                  >
                    {seriesExpanded ? (
                      <>
                        <ChevronUp className="h-3 w-3 mr-1" />
                        Show less
                      </>
                    ) : (
                      <>
                        <ChevronDown className="h-3 w-3 mr-1" />
                        Show all {stats.series_types.length} types
                      </>
                    )}
                  </Button>
                )}
              </div>
            )}

            {/* Event Types */}
            {stats.event_types.length > 0 && (
              <div>
                <h3 className="text-xs font-medium text-zinc-400 mb-3">
                  Events ({stats.event_types.length})
                </h3>
                <div className="space-y-2">
                  {visibleEvents?.map((metric) => (
                    <div
                      key={`${metric.category}-${metric.type}`}
                      className="flex items-center justify-between"
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-zinc-500 bg-zinc-800 px-1.5 py-0.5 rounded capitalize">
                          {metric.category}
                        </span>
                        <span className="text-sm text-zinc-300">
                          {metric.type || 'Unknown'}
                        </span>
                      </div>
                      <span className="text-sm font-medium text-white">
                        {metric.count.toLocaleString()}
                      </span>
                    </div>
                  ))}
                </div>
                {stats.event_types.length > COLLAPSED_LIMIT && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setEventsExpanded(!eventsExpanded)}
                    className="mt-2 text-xs text-zinc-500 hover:text-zinc-300 px-0"
                  >
                    {eventsExpanded ? (
                      <>
                        <ChevronUp className="h-3 w-3 mr-1" />
                        Show less
                      </>
                    ) : (
                      <>
                        <ChevronDown className="h-3 w-3 mr-1" />
                        Show all {stats.event_types.length} types
                      </>
                    )}
                  </Button>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

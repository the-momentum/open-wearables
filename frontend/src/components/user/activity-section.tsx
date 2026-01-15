import { useMemo } from 'react';
import { format } from 'date-fns';
import {
  Activity,
  Flame,
  Footprints,
  Heart,
  Timer,
  TrendingUp,
  MoveHorizontal,
  Armchair,
} from 'lucide-react';
import { useActivitySummaries } from '@/hooks/api/use-health';
import {
  DateRangeSelector,
  type DateRangeValue,
} from '@/components/ui/date-range-selector';
import type { ActivitySummary } from '@/lib/api/types';

interface ActivitySectionProps {
  userId: string;
  dateRange: DateRangeValue;
  onDateRangeChange: (value: DateRangeValue) => void;
}

function formatNumber(value: number | null): string {
  if (value === null) return '-';
  return value.toLocaleString();
}

function formatDistance(meters: number | null): string {
  if (meters === null) return '-';
  const km = meters / 1000;
  if (km >= 1) {
    return `${km.toFixed(1)} km`;
  }
  return `${Math.round(meters)} m`;
}

function formatMinutes(minutes: number | null): string {
  if (minutes === null) return '-';
  const hours = Math.floor(minutes / 60);
  const mins = Math.round(minutes % 60);
  if (hours === 0) return `${mins}m`;
  return `${hours}h ${mins}m`;
}

// Loading skeleton
function ActivitySectionSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30"
          >
            <div className="h-5 w-5 bg-zinc-800 rounded animate-pulse mb-3" />
            <div className="h-7 w-20 bg-zinc-800 rounded animate-pulse mb-1" />
            <div className="h-4 w-24 bg-zinc-800/50 rounded animate-pulse" />
          </div>
        ))}
      </div>
    </div>
  );
}

// Recent activity day card
function ActivityDayCard({ summary }: { summary: ActivitySummary }) {
  return (
    <div className="p-3 bg-zinc-800/50 border border-zinc-700/50 rounded-lg">
      {/* Header: Date */}
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-zinc-200">
          {format(new Date(summary.date), 'EEE, MMM d')}
        </span>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-4 gap-3">
        {/* Steps */}
        <div className="flex flex-col items-center text-center">
          <Footprints className="h-3.5 w-3.5 text-emerald-400 mb-1" />
          <span className="text-sm font-medium text-white">
            {formatNumber(summary.steps)}
          </span>
          <span className="text-[10px] text-zinc-500">steps</span>
        </div>

        {/* Calories */}
        <div className="flex flex-col items-center text-center">
          <Flame className="h-3.5 w-3.5 text-orange-400 mb-1" />
          <span className="text-sm font-medium text-white">
            {formatNumber(summary.active_calories_kcal)}
          </span>
          <span className="text-[10px] text-zinc-500">cal</span>
        </div>

        {/* Distance */}
        <div className="flex flex-col items-center text-center">
          <MoveHorizontal className="h-3.5 w-3.5 text-purple-400 mb-1" />
          <span className="text-sm font-medium text-white">
            {formatDistance(summary.distance_meters)}
          </span>
          <span className="text-[10px] text-zinc-500">distance</span>
        </div>

        {/* Active Time */}
        <div className="flex flex-col items-center text-center">
          <Timer className="h-3.5 w-3.5 text-sky-400 mb-1" />
          <span className="text-sm font-medium text-white">
            {formatMinutes(summary.active_minutes)}
          </span>
          <span className="text-[10px] text-zinc-500">active</span>
        </div>
      </div>
    </div>
  );
}

export function ActivitySection({
  userId,
  dateRange,
  onDateRangeChange,
}: ActivitySectionProps) {
  // Calculate date range
  const { startDate, endDate } = useMemo(() => {
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - dateRange);
    return {
      startDate: start.toISOString(),
      endDate: end.toISOString(),
    };
  }, [dateRange]);

  // Fetch activity summaries
  const { data: activitySummaries, isLoading } = useActivitySummaries(userId, {
    start_date: startDate,
    end_date: endDate,
    limit: 100,
  });

  // Calculate aggregate statistics
  const stats = useMemo(() => {
    const summaries = activitySummaries?.data || [];
    if (summaries.length === 0) {
      return null;
    }

    // Sum totals
    const totalSteps = summaries.reduce((acc, s) => acc + (s.steps || 0), 0);
    const totalCalories = summaries.reduce(
      (acc, s) => acc + (s.active_calories_kcal || 0),
      0
    );
    const totalDistance = summaries.reduce(
      (acc, s) => acc + (s.distance_meters || 0),
      0
    );
    const totalActiveMinutes = summaries.reduce(
      (acc, s) => acc + (s.active_minutes || 0),
      0
    );
    const totalFloorsClimbed = summaries.reduce(
      (acc, s) => acc + (s.floors_climbed || 0),
      0
    );
    const totalSedentaryMinutes = summaries.reduce(
      (acc, s) => acc + (s.sedentary_minutes || 0),
      0
    );

    // Calculate averages
    const daysWithSteps = summaries.filter((s) => s.steps !== null).length;
    const daysWithCalories = summaries.filter(
      (s) => s.active_calories_kcal !== null
    ).length;

    // Heart rate stats (average of daily averages)
    const heartRates = summaries
      .map((s) => s.heart_rate?.avg_bpm)
      .filter((hr): hr is number => hr !== null);
    const avgHeartRate =
      heartRates.length > 0
        ? heartRates.reduce((a, b) => a + b, 0) / heartRates.length
        : null;

    return {
      totalSteps,
      avgSteps: daysWithSteps > 0 ? Math.round(totalSteps / daysWithSteps) : 0,
      totalCalories,
      avgCalories:
        daysWithCalories > 0 ? Math.round(totalCalories / daysWithCalories) : 0,
      totalDistance,
      totalActiveMinutes,
      totalFloorsClimbed,
      totalSedentaryMinutes,
      avgHeartRate,
      daysTracked: summaries.length,
    };
  }, [activitySummaries]);

  // Get recent days (sorted by date descending)
  const recentDays = useMemo(() => {
    const summaries = activitySummaries?.data || [];
    return [...summaries]
      .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
      .slice(0, 5);
  }, [activitySummaries]);

  const hasData = (activitySummaries?.data?.length || 0) > 0;

  return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
      <div className="px-6 py-4 border-b border-zinc-800 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h3 className="text-sm font-medium text-white">Activity</h3>
          <DateRangeSelector value={dateRange} onChange={onDateRangeChange} />
        </div>
        <Activity className="h-4 w-4 text-zinc-500" />
      </div>

      <div className="p-6">
        {isLoading ? (
          <ActivitySectionSkeleton />
        ) : !hasData ? (
          <p className="text-sm text-zinc-500 text-center py-8">
            No activity data available yet
          </p>
        ) : (
          <div className="space-y-6">
            {/* Summary Stats - Top Row */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {/* Total Steps */}
              <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                <div className="flex items-center gap-3 mb-3">
                  <div className="p-2 bg-emerald-500/10 rounded-lg">
                    <Footprints className="h-5 w-5 text-emerald-400" />
                  </div>
                </div>
                <p className="text-2xl font-semibold text-white">
                  {formatNumber(stats?.totalSteps || 0)}
                </p>
                <p className="text-xs text-zinc-500 mt-1">
                  Total Steps ({stats?.avgSteps?.toLocaleString() || 0}/day avg)
                </p>
              </div>

              {/* Active Calories */}
              <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                <div className="flex items-center gap-3 mb-3">
                  <div className="p-2 bg-orange-500/10 rounded-lg">
                    <Flame className="h-5 w-5 text-orange-400" />
                  </div>
                </div>
                <p className="text-2xl font-semibold text-white">
                  {formatNumber(stats?.totalCalories || 0)}
                </p>
                <p className="text-xs text-zinc-500 mt-1">
                  Active Calories ({stats?.avgCalories?.toLocaleString() || 0}
                  /day)
                </p>
              </div>

              {/* Active Time */}
              <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                <div className="flex items-center gap-3 mb-3">
                  <div className="p-2 bg-sky-500/10 rounded-lg">
                    <Timer className="h-5 w-5 text-sky-400" />
                  </div>
                </div>
                <p className="text-2xl font-semibold text-white">
                  {formatMinutes(stats?.totalActiveMinutes || 0)}
                </p>
                <p className="text-xs text-zinc-500 mt-1">Total Active Time</p>
              </div>

              {/* Avg Heart Rate */}
              <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                <div className="flex items-center gap-3 mb-3">
                  <div className="p-2 bg-rose-500/10 rounded-lg">
                    <Heart className="h-5 w-5 text-rose-400" />
                  </div>
                </div>
                <p className="text-2xl font-semibold text-white">
                  {stats?.avgHeartRate ? Math.round(stats.avgHeartRate) : '-'}
                </p>
                <p className="text-xs text-zinc-500 mt-1">Avg Heart Rate</p>
              </div>
            </div>

            {/* Two-column layout: Distance + Recent Days */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Summary Stats */}
              <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                <h4 className="text-xs font-medium text-zinc-400 mb-4 uppercase tracking-wider">
                  Summary
                </h4>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <MoveHorizontal className="h-4 w-4 text-purple-400" />
                      <span className="text-sm text-zinc-300">
                        Total Distance
                      </span>
                    </div>
                    <span className="text-sm font-medium text-white">
                      {formatDistance(stats?.totalDistance || 0)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <TrendingUp className="h-4 w-4 text-amber-400" />
                      <span className="text-sm text-zinc-300">
                        Floors Climbed
                      </span>
                    </div>
                    <span className="text-sm font-medium text-white">
                      {formatNumber(stats?.totalFloorsClimbed || 0)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Armchair className="h-4 w-4 text-zinc-400" />
                      <span className="text-sm text-zinc-300">
                        Sedentary Time
                      </span>
                    </div>
                    <span className="text-sm font-medium text-white">
                      {formatMinutes(stats?.totalSedentaryMinutes || 0)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Activity className="h-4 w-4 text-indigo-400" />
                      <span className="text-sm text-zinc-300">
                        Days Tracked
                      </span>
                    </div>
                    <span className="text-sm font-medium text-white">
                      {stats?.daysTracked || 0}
                    </span>
                  </div>
                </div>
              </div>

              {/* Recent Days */}
              <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                <h4 className="text-xs font-medium text-zinc-400 mb-4 uppercase tracking-wider">
                  Recent Days
                </h4>
                {recentDays.length > 0 ? (
                  <div className="space-y-3">
                    {recentDays.map((summary) => (
                      <ActivityDayCard key={summary.date} summary={summary} />
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-zinc-500">No recent activity</p>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

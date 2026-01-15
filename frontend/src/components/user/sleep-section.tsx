import { useMemo } from 'react';
import { format } from 'date-fns';
import { Moon, Zap, Clock, BedDouble } from 'lucide-react';
import { useSleepSessions, useSleepSummaries } from '@/hooks/api/use-health';
import {
  DateRangeSelector,
  type DateRangeValue,
} from '@/components/ui/date-range-selector';
import type { SleepSession, SleepStagesSummary } from '@/lib/api/types';

interface SleepSectionProps {
  userId: string;
  dateRange: DateRangeValue;
  onDateRangeChange: (value: DateRangeValue) => void;
}

// Color mapping for sleep stages
const STAGE_COLORS = {
  deep: 'bg-indigo-500',
  rem: 'bg-purple-500',
  light: 'bg-sky-400',
  awake: 'bg-zinc-500',
} as const;

const STAGE_LABELS = {
  deep: 'Deep',
  rem: 'REM',
  light: 'Light',
  awake: 'Awake',
} as const;

function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours === 0) return `${minutes}m`;
  return `${hours}h ${minutes}m`;
}

function formatMinutes(minutes: number | null): string {
  if (minutes === null) return '-';
  const hours = Math.floor(minutes / 60);
  const mins = Math.round(minutes % 60);
  if (hours === 0) return `${mins}m`;
  return `${hours}h ${mins}m`;
}

function formatBedtime(minutes: number | null): string {
  if (minutes === null) return '-';
  // Handle wrap-around for late nights
  const normalizedMinutes = minutes >= 1440 ? minutes - 1440 : minutes;
  const hours = Math.floor(normalizedMinutes / 60);
  const mins = Math.round(normalizedMinutes % 60);
  const period = hours >= 12 ? 'PM' : 'AM';
  const displayHours = hours > 12 ? hours - 12 : hours === 0 ? 12 : hours;
  return `${displayHours}:${mins.toString().padStart(2, '0')} ${period}`;
}

// Component for visualizing sleep stages as a horizontal bar
function SleepStagesBar({
  stages,
  className = '',
}: {
  stages: SleepStagesSummary | null;
  className?: string;
}) {
  if (!stages) {
    return (
      <div className={`h-2 bg-zinc-700 rounded-full ${className}`}>
        <div className="h-full w-full bg-zinc-600 rounded-full" />
      </div>
    );
  }

  const total =
    (stages.deep_minutes || 0) +
    (stages.rem_minutes || 0) +
    (stages.light_minutes || 0) +
    (stages.awake_minutes || 0);

  if (total === 0) {
    return (
      <div className={`h-2 bg-zinc-700 rounded-full ${className}`}>
        <div className="h-full w-full bg-zinc-600 rounded-full" />
      </div>
    );
  }

  const deepPct = ((stages.deep_minutes || 0) / total) * 100;
  const remPct = ((stages.rem_minutes || 0) / total) * 100;
  const lightPct = ((stages.light_minutes || 0) / total) * 100;
  const awakePct = ((stages.awake_minutes || 0) / total) * 100;

  return (
    <div
      className={`h-2 bg-zinc-700 rounded-full overflow-hidden flex ${className}`}
    >
      {deepPct > 0 && (
        <div
          className={`${STAGE_COLORS.deep}`}
          style={{ width: `${deepPct}%` }}
        />
      )}
      {remPct > 0 && (
        <div
          className={`${STAGE_COLORS.rem}`}
          style={{ width: `${remPct}%` }}
        />
      )}
      {lightPct > 0 && (
        <div
          className={`${STAGE_COLORS.light}`}
          style={{ width: `${lightPct}%` }}
        />
      )}
      {awakePct > 0 && (
        <div
          className={`${STAGE_COLORS.awake}`}
          style={{ width: `${awakePct}%` }}
        />
      )}
    </div>
  );
}

// Component for a single sleep session card
function SleepSessionCard({ session }: { session: SleepSession }) {
  return (
    <div className="p-3 bg-zinc-800/50 border border-zinc-700/50 rounded-lg">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-zinc-200">
            {format(new Date(session.start_time), 'MMM d')}
          </span>
          {session.is_nap && (
            <span className="text-[10px] font-medium px-1.5 py-0.5 bg-amber-500/20 text-amber-400 rounded">
              NAP
            </span>
          )}
        </div>
        <div className="flex items-center gap-3 text-xs text-zinc-400">
          <span>{formatDuration(session.duration_seconds)}</span>
          {session.efficiency_percent !== null && (
            <span className="text-emerald-400">
              {Math.round(session.efficiency_percent)}%
            </span>
          )}
        </div>
      </div>
      <SleepStagesBar stages={session.stages} />
      <div className="mt-2 flex items-center gap-1 text-[10px] text-zinc-500">
        <span>{format(new Date(session.start_time), 'h:mm a')}</span>
        <span>→</span>
        <span>{format(new Date(session.end_time), 'h:mm a')}</span>
      </div>
    </div>
  );
}

// Loading skeleton
function SleepSectionSkeleton() {
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

export function SleepSection({
  userId,
  dateRange,
  onDateRangeChange,
}: SleepSectionProps) {
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

  // Fetch sleep sessions
  const { data: sleepSessions, isLoading: sessionsLoading } = useSleepSessions(
    userId,
    {
      start_date: startDate,
      end_date: endDate,
      limit: 50,
    }
  );

  // Fetch sleep summaries for aggregate stats
  const { data: sleepSummaries, isLoading: summariesLoading } =
    useSleepSummaries(userId, {
      start_date: startDate,
      end_date: endDate,
      limit: 100,
    });

  const isLoading = sessionsLoading || summariesLoading;

  // Calculate aggregate statistics from summaries
  const stats = useMemo(() => {
    const summaries = sleepSummaries?.data || [];
    if (summaries.length === 0) {
      return null;
    }

    // Filter out null values for averaging
    const durations = summaries
      .map((s) => s.duration_minutes)
      .filter((d): d is number => d !== null);
    const efficiencies = summaries
      .map((s) => s.efficiency_percent)
      .filter((e): e is number => e !== null);

    // Aggregate sleep stages
    const totalDeep = summaries.reduce(
      (acc, s) => acc + (s.stages?.deep_minutes || 0),
      0
    );
    const totalRem = summaries.reduce(
      (acc, s) => acc + (s.stages?.rem_minutes || 0),
      0
    );
    const totalLight = summaries.reduce(
      (acc, s) => acc + (s.stages?.light_minutes || 0),
      0
    );
    const totalAwake = summaries.reduce(
      (acc, s) => acc + (s.stages?.awake_minutes || 0),
      0
    );
    const totalStages = totalDeep + totalRem + totalLight + totalAwake;

    // Calculate average bedtime
    const bedtimes = summaries
      .map((s) => s.start_time)
      .filter((t): t is string => t !== null)
      .map((t) => {
        const date = new Date(t);
        // Convert to minutes from midnight, handling late night times
        let minutes = date.getHours() * 60 + date.getMinutes();
        // If before 6am, treat as previous day's evening
        if (minutes < 360) minutes += 1440;
        return minutes;
      });

    const avgBedtimeMinutes =
      bedtimes.length > 0
        ? bedtimes.reduce((a, b) => a + b, 0) / bedtimes.length
        : null;

    return {
      avgDuration:
        durations.length > 0
          ? durations.reduce((a, b) => a + b, 0) / durations.length
          : null,
      avgEfficiency:
        efficiencies.length > 0
          ? efficiencies.reduce((a, b) => a + b, 0) / efficiencies.length
          : null,
      sessionCount: sleepSessions?.data?.filter((s) => !s.is_nap).length || 0,
      avgBedtime: avgBedtimeMinutes,
      stages:
        totalStages > 0
          ? {
              deep: {
                minutes: totalDeep,
                percent: (totalDeep / totalStages) * 100,
              },
              rem: {
                minutes: totalRem,
                percent: (totalRem / totalStages) * 100,
              },
              light: {
                minutes: totalLight,
                percent: (totalLight / totalStages) * 100,
              },
              awake: {
                minutes: totalAwake,
                percent: (totalAwake / totalStages) * 100,
              },
            }
          : null,
    };
  }, [sleepSummaries, sleepSessions]);

  // Get recent sessions (non-naps first, limited to 5)
  const recentSessions = useMemo(() => {
    const sessions = sleepSessions?.data || [];
    // Sort by start_time descending and take first 5
    return [...sessions]
      .sort(
        (a, b) =>
          new Date(b.start_time).getTime() - new Date(a.start_time).getTime()
      )
      .slice(0, 5);
  }, [sleepSessions]);

  const hasData = useMemo(
    () =>
      (sleepSessions?.data?.length || 0) > 0 ||
      (sleepSummaries?.data?.length || 0) > 0,
    [sleepSessions?.data?.length, sleepSummaries?.data?.length]
  );

  return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
      <div className="px-6 py-4 border-b border-zinc-800 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h3 className="text-sm font-medium text-white">Sleep</h3>
          <DateRangeSelector value={dateRange} onChange={onDateRangeChange} />
        </div>
        <Moon className="h-4 w-4 text-zinc-500" />
      </div>

      <div className="p-6">
        {isLoading ? (
          <SleepSectionSkeleton />
        ) : !hasData ? (
          <p className="text-sm text-zinc-500 text-center py-8">
            No sleep data available yet
          </p>
        ) : (
          <div className="space-y-6">
            {/* Summary Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {/* Average Duration */}
              <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                <div className="flex items-center gap-3 mb-3">
                  <div className="p-2 bg-indigo-500/10 rounded-lg">
                    <Moon className="h-5 w-5 text-indigo-400" />
                  </div>
                </div>
                <p className="text-2xl font-semibold text-white">
                  {stats?.avgDuration ? formatMinutes(stats.avgDuration) : '-'}
                </p>
                <p className="text-xs text-zinc-500 mt-1">Avg Duration</p>
              </div>

              {/* Average Efficiency */}
              <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                <div className="flex items-center gap-3 mb-3">
                  <div className="p-2 bg-emerald-500/10 rounded-lg">
                    <Zap className="h-5 w-5 text-emerald-400" />
                  </div>
                </div>
                <p className="text-2xl font-semibold text-white">
                  {stats?.avgEfficiency !== null &&
                  stats?.avgEfficiency !== undefined
                    ? `${Math.round(stats.avgEfficiency)}%`
                    : '-'}
                </p>
                <p className="text-xs text-zinc-500 mt-1">Avg Efficiency</p>
              </div>

              {/* Session Count */}
              <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                <div className="flex items-center gap-3 mb-3">
                  <div className="p-2 bg-purple-500/10 rounded-lg">
                    <BedDouble className="h-5 w-5 text-purple-400" />
                  </div>
                </div>
                <p className="text-2xl font-semibold text-white">
                  {stats?.sessionCount || 0}
                </p>
                <p className="text-xs text-zinc-500 mt-1">Nights Tracked</p>
              </div>

              {/* Average Bedtime */}
              <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                <div className="flex items-center gap-3 mb-3">
                  <div className="p-2 bg-sky-500/10 rounded-lg">
                    <Clock className="h-5 w-5 text-sky-400" />
                  </div>
                </div>
                <p className="text-2xl font-semibold text-white">
                  {formatBedtime(stats?.avgBedtime || null)}
                </p>
                <p className="text-xs text-zinc-500 mt-1">Avg Bedtime</p>
              </div>
            </div>

            {/* Two-column layout: Stages + Recent Sessions */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Sleep Stages Breakdown */}
              <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                <h4 className="text-xs font-medium text-zinc-400 mb-4 uppercase tracking-wider">
                  Sleep Stages (Average)
                </h4>
                {stats?.stages ? (
                  <div className="space-y-4">
                    {/* Visual bar */}
                    <div className="h-3 bg-zinc-700 rounded-full overflow-hidden flex">
                      {stats.stages.deep.percent > 0 && (
                        <div
                          className={STAGE_COLORS.deep}
                          style={{ width: `${stats.stages.deep.percent}%` }}
                        />
                      )}
                      {stats.stages.rem.percent > 0 && (
                        <div
                          className={STAGE_COLORS.rem}
                          style={{ width: `${stats.stages.rem.percent}%` }}
                        />
                      )}
                      {stats.stages.light.percent > 0 && (
                        <div
                          className={STAGE_COLORS.light}
                          style={{ width: `${stats.stages.light.percent}%` }}
                        />
                      )}
                      {stats.stages.awake.percent > 0 && (
                        <div
                          className={STAGE_COLORS.awake}
                          style={{ width: `${stats.stages.awake.percent}%` }}
                        />
                      )}
                    </div>

                    {/* Legend */}
                    <div className="grid grid-cols-2 gap-3">
                      {(['deep', 'rem', 'light', 'awake'] as const).map(
                        (stage) => (
                          <div key={stage} className="flex items-center gap-2">
                            <div
                              className={`w-3 h-3 rounded-sm ${STAGE_COLORS[stage]}`}
                            />
                            <div className="flex-1">
                              <span className="text-xs text-zinc-300">
                                {STAGE_LABELS[stage]}
                              </span>
                            </div>
                            <span className="text-xs text-zinc-500">
                              {Math.round(stats.stages![stage].percent)}%
                            </span>
                          </div>
                        )
                      )}
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-zinc-500">
                    No stage data available
                  </p>
                )}
              </div>

              {/* Recent Sessions */}
              <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                <h4 className="text-xs font-medium text-zinc-400 mb-4 uppercase tracking-wider">
                  Recent Sessions
                </h4>
                {recentSessions.length > 0 ? (
                  <div className="space-y-3">
                    {recentSessions.map((session) => (
                      <SleepSessionCard key={session.id} session={session} />
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-zinc-500">No recent sessions</p>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

import { useMemo, useState } from 'react';
import { format } from 'date-fns';
import {
  Moon,
  Zap,
  Clock,
  BedDouble,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { useSleepSessions, useSleepSummaries } from '@/hooks/api/use-health';
import { useCursorPagination } from '@/hooks/use-cursor-pagination';
import {
  DateRangeSelector,
  type DateRangeValue,
} from '@/components/ui/date-range-selector';
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import type { SleepSession, SleepStagesSummary } from '@/lib/api/types';

interface SleepSectionProps {
  userId: string;
  dateRange: DateRangeValue;
  onDateRangeChange: (value: DateRangeValue) => void;
}

const SESSIONS_PER_PAGE = 10;

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

  const stageData = [
    {
      key: 'deep',
      minutes: stages.deep_minutes || 0,
      pct: ((stages.deep_minutes || 0) / total) * 100,
      color: STAGE_COLORS.deep,
      label: STAGE_LABELS.deep,
    },
    {
      key: 'rem',
      minutes: stages.rem_minutes || 0,
      pct: ((stages.rem_minutes || 0) / total) * 100,
      color: STAGE_COLORS.rem,
      label: STAGE_LABELS.rem,
    },
    {
      key: 'light',
      minutes: stages.light_minutes || 0,
      pct: ((stages.light_minutes || 0) / total) * 100,
      color: STAGE_COLORS.light,
      label: STAGE_LABELS.light,
    },
    {
      key: 'awake',
      minutes: stages.awake_minutes || 0,
      pct: ((stages.awake_minutes || 0) / total) * 100,
      color: STAGE_COLORS.awake,
      label: STAGE_LABELS.awake,
    },
  ];

  return (
    <div
      className={`h-2 bg-zinc-700 rounded-full overflow-hidden flex ${className}`}
    >
      {stageData.map(
        (stage) =>
          stage.pct > 0 && (
            <Tooltip key={stage.key}>
              <TooltipTrigger asChild>
                <div
                  className={`${stage.color} cursor-pointer hover:opacity-80 transition-opacity`}
                  style={{ width: `${stage.pct}%` }}
                />
              </TooltipTrigger>
              <TooltipContent>
                <p>
                  {stage.label}: {formatMinutes(stage.minutes)} (
                  {Math.round(stage.pct)}%)
                </p>
              </TooltipContent>
            </Tooltip>
          )
      )}
    </div>
  );
}

// Expandable sleep session row
function SleepSessionRow({ session }: { session: SleepSession }) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Collect all available detail fields (expanded view)
  const detailFields = useMemo(() => {
    const fields: { label: string; value: string }[] = [];

    // Stage details
    if (session.stages?.deep_minutes != null) {
      fields.push({
        label: 'Deep Sleep',
        value: formatMinutes(session.stages.deep_minutes),
      });
    }
    if (session.stages?.rem_minutes != null) {
      fields.push({
        label: 'REM Sleep',
        value: formatMinutes(session.stages.rem_minutes),
      });
    }
    if (session.stages?.light_minutes != null) {
      fields.push({
        label: 'Light Sleep',
        value: formatMinutes(session.stages.light_minutes),
      });
    }
    if (session.stages?.awake_minutes != null) {
      fields.push({
        label: 'Time Awake',
        value: formatMinutes(session.stages.awake_minutes),
      });
    }

    // Source
    if (session.source?.provider) {
      fields.push({ label: 'Source', value: session.source.provider });
    }

    return fields;
  }, [session]);

  const hasDetails = detailFields.length > 0;

  return (
    <div className="border border-zinc-800 rounded-lg overflow-hidden bg-zinc-900/30 hover:bg-zinc-900/50 transition-colors">
      {/* Main row - always visible */}
      <button
        onClick={() => hasDetails && setIsExpanded(!isExpanded)}
        className="w-full px-4 py-3 flex items-center text-left"
        disabled={!hasDetails}
      >
        {/* Date */}
        <div className="w-28 flex-shrink-0">
          {session.is_nap && (
            <span className="text-[10px] font-medium px-1.5 py-0.5 bg-amber-500/20 text-amber-400 rounded">
              NAP
            </span>
          )}
          <div className="flex items-center gap-2">
            <p className="text-sm font-medium text-white">
              {format(new Date(session.start_time), 'EEE, MMM d')}
            </p>
          </div>
          <p className="text-xs text-zinc-500">
            {format(new Date(session.start_time), 'yyyy')}
          </p>
        </div>

        {/* Right side - Top: Stages bar, Bottom: Stats */}
        <div className="flex-1 flex flex-col gap-2 mx-4">
          {/* Top: Sleep Stages Bar */}
          <SleepStagesBar stages={session.stages} className="h-3 mb-4" />

          {/* Bottom: Stats - evenly spaced */}
          <div className="flex items-center justify-around">
            {/* Efficiency */}
            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-emerald-400" />
              <div>
                <p className="text-sm font-medium text-white">
                  {session.efficiency_percent != null
                    ? `${Math.round(session.efficiency_percent)}%`
                    : '-'}
                </p>
                <p className="text-xs text-zinc-500">Efficiency</p>
              </div>
            </div>

            {/* Duration */}
            <div className="flex items-center gap-2">
              <Moon className="h-4 w-4 text-indigo-400" />
              <div>
                <p className="text-sm font-medium text-white">
                  {formatDuration(session.duration_seconds)}
                </p>
                <p className="text-xs text-zinc-500">Duration</p>
              </div>
            </div>

            {/* Bedtime */}
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-sky-400" />
              <div>
                <p className="text-sm font-medium text-white">
                  {format(new Date(session.start_time), 'h:mm a')}
                </p>
                <p className="text-xs text-zinc-500">Bedtime</p>
              </div>
            </div>

            {/* Wake Time */}
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-amber-400" />
              <div>
                <p className="text-sm font-medium text-white">
                  {format(new Date(session.end_time), 'h:mm a')}
                </p>
                <p className="text-xs text-zinc-500">Wake</p>
              </div>
            </div>
          </div>
        </div>

        {/* Expand indicator */}
        {hasDetails && (
          <div className="w-8 flex-shrink-0 flex justify-end ml-2">
            {isExpanded ? (
              <ChevronUp className="h-5 w-5 text-zinc-400" />
            ) : (
              <ChevronDown className="h-5 w-5 text-zinc-400" />
            )}
          </div>
        )}
      </button>

      {/* Expanded details */}
      {isExpanded && detailFields.length > 0 && (
        <div className="px-4 pb-4 pt-2 border-t border-zinc-800">
          <div className="flex gap-6">
            {/* Left column */}
            <div className="flex-1 space-y-2">
              {detailFields
                .slice(0, Math.ceil(detailFields.length / 2))
                .map((field) => (
                  <div
                    key={field.label}
                    className="flex items-center justify-between py-1"
                  >
                    <span className="text-sm text-zinc-500">{field.label}</span>
                    <span className="text-sm font-medium text-white">
                      {field.value}
                    </span>
                  </div>
                ))}
            </div>

            {/* Divider */}
            <div className="w-px bg-zinc-800" />

            {/* Right column */}
            <div className="flex-1 space-y-2">
              {detailFields
                .slice(Math.ceil(detailFields.length / 2))
                .map((field) => (
                  <div
                    key={field.label}
                    className="flex items-center justify-between py-1"
                  >
                    <span className="text-sm text-zinc-500">{field.label}</span>
                    <span className="text-sm font-medium text-white">
                      {field.value}
                    </span>
                  </div>
                ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Loading skeleton
function SleepSectionSkeleton() {
  return (
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
  );
}

function SessionsListSkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2, 3, 4, 5].map((i) => (
        <div
          key={i}
          className="px-4 py-3 border border-zinc-800 rounded-lg bg-zinc-900/30"
        >
          <div className="flex items-center">
            <div className="w-28 flex-shrink-0">
              <div className="h-5 w-20 bg-zinc-800 rounded animate-pulse" />
              <div className="h-3 w-12 bg-zinc-800/50 rounded animate-pulse mt-1" />
            </div>
            <div className="flex-1 flex items-center justify-around">
              {[1, 2, 3].map((j) => (
                <div key={j} className="flex items-center gap-2">
                  <div className="h-4 w-4 bg-zinc-800 rounded animate-pulse" />
                  <div>
                    <div className="h-4 w-12 bg-zinc-800 rounded animate-pulse" />
                    <div className="h-3 w-10 bg-zinc-800/50 rounded animate-pulse mt-1" />
                  </div>
                </div>
              ))}
              <div className="w-24 h-2 bg-zinc-800 rounded-full animate-pulse" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export function SleepSection({
  userId,
  dateRange,
  onDateRangeChange,
}: SleepSectionProps) {
  // Cursor-based pagination for sleep sessions
  const pagination = useCursorPagination();

  // Calculate date range for summary
  const { startDate, endDate } = useMemo(() => {
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - dateRange);
    return {
      startDate: start.toISOString(),
      endDate: end.toISOString(),
    };
  }, [dateRange]);

  // Wide date range for fetching sleep sessions
  const allTimeRange = useMemo(() => {
    const start = new Date('2000-01-01');
    const end = new Date();
    return {
      start_date: start.toISOString(),
      end_date: end.toISOString(),
    };
  }, []);

  // Fetch sleep summaries for summary stats (date range filtered)
  const { data: sleepSummaries, isLoading: summaryLoading } = useSleepSummaries(
    userId,
    {
      start_date: startDate,
      end_date: endDate,
      limit: 100,
    }
  );

  // Fetch sleep sessions with cursor-based pagination
  const {
    data: sessionsData,
    isLoading: sessionsLoading,
    isFetching,
  } = useSleepSessions(userId, {
    ...allTimeRange,
    limit: SESSIONS_PER_PAGE,
    cursor: pagination.currentCursor ?? undefined,
  });

  // Derive pagination state from response
  const nextCursor = sessionsData?.pagination?.next_cursor ?? null;
  const hasNextPage = sessionsData?.pagination?.has_more ?? false;

  const handleNextPage = () => pagination.goToNextPage(nextCursor);
  const handlePrevPage = pagination.goToPrevPage;

  // Calculate aggregate statistics from date-range filtered summaries
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

    // Aggregate sleep stages (calculate averages)
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
    const nightCount = summaries.length;
    const avgDeep = nightCount > 0 ? totalDeep / nightCount : 0;
    const avgRem = nightCount > 0 ? totalRem / nightCount : 0;
    const avgLight = nightCount > 0 ? totalLight / nightCount : 0;
    const avgAwake = nightCount > 0 ? totalAwake / nightCount : 0;
    const avgStagesTotal = avgDeep + avgRem + avgLight + avgAwake;

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
      nightsTracked: summaries.length,
      avgBedtime: avgBedtimeMinutes,
      // Use SleepStagesSummary format so we can reuse SleepStagesBar
      // Store averages (not totals) so tooltip shows avg per night
      stages:
        avgStagesTotal > 0
          ? {
              deep_minutes: avgDeep,
              rem_minutes: avgRem,
              light_minutes: avgLight,
              awake_minutes: avgAwake,
            }
          : null,
      stagesTotal: avgStagesTotal,
    };
  }, [sleepSummaries]);

  // Get displayed sessions from current page data
  const displayedSessions = sessionsData?.data || [];
  const hasData = displayedSessions.length > 0;

  return (
    <div className="space-y-6">
      {/* Summary Section */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-zinc-800 flex items-center justify-between">
          <h3 className="text-sm font-medium text-white">Sleep Summary</h3>
          <DateRangeSelector value={dateRange} onChange={onDateRangeChange} />
        </div>

        <div className="p-6">
          {summaryLoading ? (
            <SleepSectionSkeleton />
          ) : !stats ? (
            <p className="text-sm text-zinc-500 text-center py-4">
              No sleep data in this period
            </p>
          ) : (
            <div className="space-y-6">
              {/* Summary Stats - Top Row */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {/* Nights Tracked */}
                <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 bg-purple-500/10 rounded-lg">
                      <BedDouble className="h-5 w-5 text-purple-400" />
                    </div>
                  </div>
                  <p className="text-2xl font-semibold text-white">
                    {stats.nightsTracked}
                  </p>
                  <p className="text-xs text-zinc-500 mt-1">Nights Tracked</p>
                </div>

                {/* Average Efficiency */}
                <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 bg-emerald-500/10 rounded-lg">
                      <Zap className="h-5 w-5 text-emerald-400" />
                    </div>
                  </div>
                  <p className="text-2xl font-semibold text-white">
                    {stats.avgEfficiency != null
                      ? `${Math.round(stats.avgEfficiency)}%`
                      : '-'}
                  </p>
                  <p className="text-xs text-zinc-500 mt-1">Avg Efficiency</p>
                </div>

                {/* Average Duration */}
                <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 bg-indigo-500/10 rounded-lg">
                      <Moon className="h-5 w-5 text-indigo-400" />
                    </div>
                  </div>
                  <p className="text-2xl font-semibold text-white">
                    {stats.avgDuration ? formatMinutes(stats.avgDuration) : '-'}
                  </p>
                  <p className="text-xs text-zinc-500 mt-1">Avg Duration</p>
                </div>

                {/* Average Bedtime */}
                <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 bg-sky-500/10 rounded-lg">
                      <Clock className="h-5 w-5 text-sky-400" />
                    </div>
                  </div>
                  <p className="text-2xl font-semibold text-white">
                    {formatBedtime(stats.avgBedtime)}
                  </p>
                  <p className="text-xs text-zinc-500 mt-1">Avg Bedtime</p>
                </div>
              </div>

              {/* Sleep Stages Breakdown */}
              {stats.stages && stats.stagesTotal > 0 && (
                <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                  <h4 className="text-xs font-medium text-zinc-400 mb-4 uppercase tracking-wider">
                    Average Sleep Stages
                  </h4>
                  <div className="space-y-4">
                    {/* Visual bar - reusing SleepStagesBar component */}
                    <SleepStagesBar stages={stats.stages} className="h-3" />

                    {/* Legend */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                      {(['deep', 'rem', 'light', 'awake'] as const).map(
                        (stage) => {
                          const key =
                            `${stage}_minutes` as keyof typeof stats.stages;
                          const minutes = stats.stages![key] || 0;
                          const percent = (minutes / stats.stagesTotal) * 100;
                          return (
                            <div
                              key={stage}
                              className="flex items-center gap-2"
                            >
                              <div
                                className={`w-3 h-3 rounded-sm ${STAGE_COLORS[stage]}`}
                              />
                              <span className="text-xs text-zinc-300">
                                {STAGE_LABELS[stage]}
                              </span>
                              <span className="text-xs text-zinc-500 ml-auto">
                                {Math.round(percent)}%
                              </span>
                            </div>
                          );
                        }
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Sleep Sessions Section */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-zinc-800 flex items-center justify-between">
          <h3 className="text-sm font-medium text-white">Sleep Sessions</h3>
          {!sessionsLoading && hasData && (
            <span className="text-xs text-zinc-500">
              Page {pagination.currentPage}
            </span>
          )}
        </div>

        <div className="p-6">
          {sessionsLoading ? (
            <SessionsListSkeleton />
          ) : displayedSessions.length === 0 ? (
            <p className="text-sm text-zinc-500 text-center py-8">
              No sleep sessions available
            </p>
          ) : (
            <div className="space-y-4">
              {/* Sessions List */}
              <div className="space-y-3">
                {displayedSessions.map((session) => (
                  <SleepSessionRow key={session.id} session={session} />
                ))}
              </div>

              {/* Pagination Controls */}
              {(pagination.hasPrevPage || hasNextPage) && (
                <div className="pt-4 border-t border-zinc-800">
                  <Pagination>
                    <PaginationContent>
                      <PaginationItem>
                        <PaginationPrevious
                          onClick={handlePrevPage}
                          className={
                            !pagination.hasPrevPage || isFetching
                              ? 'pointer-events-none opacity-50'
                              : 'cursor-pointer'
                          }
                        />
                      </PaginationItem>
                      <PaginationItem>
                        <PaginationLink isActive>
                          {pagination.currentPage}
                        </PaginationLink>
                      </PaginationItem>
                      <PaginationItem>
                        <PaginationNext
                          onClick={handleNextPage}
                          className={
                            !hasNextPage || isFetching
                              ? 'pointer-events-none opacity-50'
                              : 'cursor-pointer'
                          }
                        />
                      </PaginationItem>
                    </PaginationContent>
                  </Pagination>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

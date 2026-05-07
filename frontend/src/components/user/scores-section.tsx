import { useEffect, useMemo, useState } from 'react';
import { format } from 'date-fns';
import { Line, LineChart, CartesianGrid, XAxis, YAxis } from 'recharts';
import {
  Moon,
  Heart,
  Zap,
  Activity,
  Flame,
  Battery,
  Dumbbell,
  Shield,
  ChevronDown,
  ChevronUp,
  type LucideIcon,
} from 'lucide-react';
import { useHealthScores } from '@/hooks/api/use-health';
import { useDateRange } from '@/hooks/use-date-range';
import type { DateRangeValue } from '@/components/ui/date-range-selector';
import { SourceBadge } from '@/components/common/source-badge';
import { SectionHeader } from '@/components/common/section-header';
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from '@/components/ui/chart';
import type { HealthScoreResponse } from '@/lib/api/types';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

interface CategoryConfig {
  label: string;
  icon: LucideIcon;
  color: string;
  maxScale: number;
}

const CATEGORY_CONFIG: Record<string, CategoryConfig> = {
  sleep: {
    label: 'Sleep',
    icon: Moon,
    color: 'text-indigo-400',
    maxScale: 100,
  },
  recovery: {
    label: 'Recovery',
    icon: Heart,
    color: 'text-rose-400',
    maxScale: 100,
  },
  readiness: {
    label: 'Readiness',
    icon: Zap,
    color: 'text-[hsl(var(--success-muted))]',
    maxScale: 100,
  },
  activity: {
    label: 'Activity',
    icon: Activity,
    color: 'text-sky-400',
    maxScale: 100,
  },
  stress: {
    label: 'Stress',
    icon: Flame,
    color: 'text-orange-400',
    maxScale: 100,
  },
  body_battery: {
    label: 'Body Battery',
    icon: Battery,
    color: 'text-green-400',
    maxScale: 100,
  },
  strain: {
    label: 'Strain',
    icon: Dumbbell,
    color: 'text-[hsl(var(--destructive-muted))]',
    maxScale: 21,
  },
  resilience: {
    label: 'Resilience',
    icon: Shield,
    color: 'text-purple-400',
    maxScale: 100,
  },
};

const CATEGORY_ORDER = [
  'sleep',
  'recovery',
  'readiness',
  'activity',
  'stress',
  'body_battery',
  'strain',
  'resilience',
];

const PROVIDER_CHART_COLORS: Record<string, string> = {
  garmin: '#60a5fa',
  oura: '#a78bfa',
  whoop: '#fbbf24',
  internal: '#34d399',
  fitbit: '#2dd4bf',
  apple: '#a1a1aa',
};

const PROVIDER_LABELS: Record<string, string> = {
  garmin: 'Garmin',
  oura: 'Oura',
  whoop: 'WHOOP',
  internal: 'OW',
  fitbit: 'Fitbit',
  apple: 'Apple',
};

function getProviderColor(provider: string): string {
  return PROVIDER_CHART_COLORS[provider] || '#71717a';
}

function getProviderLabel(provider: string): string {
  return PROVIDER_LABELS[provider] || provider;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function groupScoresByDate(
  scores: HealthScoreResponse[]
): Map<string, HealthScoreResponse[]> {
  const groups = new Map<string, HealthScoreResponse[]>();
  for (const score of scores) {
    const date = score.recorded_at.split('T')[0];
    if (!groups.has(date)) groups.set(date, []);
    groups.get(date)!.push(score);
  }
  return groups;
}

function buildChartData(
  scores: HealthScoreResponse[],
  category: string
): Record<string, string | number>[] {
  const filtered = scores.filter((s) => s.category === category);
  const byDate = groupScoresByDate(filtered);

  return Array.from(byDate.entries())
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([date, dateScores]) => {
      const point: Record<string, string | number> = {
        date: format(new Date(date + 'T00:00:00'), 'MMM d'),
      };
      for (const score of dateScores) {
        if (score.value !== null && score.provider) {
          point[score.provider] =
            category === 'resilience'
              ? Number(score.value) * 100
              : Number(score.value);
        }
      }
      return point;
    });
}

function formatScore(value: number | null, category?: string): string {
  if (value === null) return '-';
  const num = Number(value);
  if (category === 'resilience') {
    return (num * 100).toFixed(1) + '%';
  }
  return Number.isInteger(num) ? String(num) : num.toFixed(1);
}

function formatComponentName(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function CategoryPill({
  label,
  icon: Icon,
  iconColor,
  isSelected,
  onClick,
}: {
  label: string;
  icon?: LucideIcon;
  iconColor?: string;
  isSelected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
        isSelected
          ? 'bg-muted-foreground/40 text-foreground border border-zinc-600'
          : 'bg-muted/50 text-muted-foreground border border-border/60 hover:border-border hover:text-foreground/90'
      }`}
    >
      {Icon && (
        <Icon
          className={`h-3.5 w-3.5 ${isSelected ? 'text-foreground' : iconColor || 'text-muted-foreground'}`}
        />
      )}
      {label}
    </button>
  );
}

function ScoreDayCard({
  date,
  scores,
}: {
  date: string;
  scores: HealthScoreResponse[];
}) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Group scores by category in defined order
  const byCategory = useMemo(() => {
    const groups = new Map<string, HealthScoreResponse[]>();
    for (const score of scores) {
      if (!groups.has(score.category)) groups.set(score.category, []);
      groups.get(score.category)!.push(score);
    }
    return new Map(
      CATEGORY_ORDER.filter((cat) => groups.has(cat)).map((cat) => [
        cat,
        groups.get(cat)!,
      ])
    );
  }, [scores]);

  const hasComponents = scores.some(
    (s) => s.components && Object.keys(s.components).length > 0
  );

  return (
    <div className="border border-border/60 rounded-lg overflow-hidden bg-card/30 hover:bg-card/40 transition-colors">
      <button
        onClick={() => hasComponents && setIsExpanded(!isExpanded)}
        className="w-full p-4 text-left"
        disabled={!hasComponents}
      >
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-medium text-foreground">
              {format(new Date(date + 'T00:00:00'), 'EEE, MMM d')}
            </p>
            <p className="text-xs text-muted-foreground">
              {format(new Date(date + 'T00:00:00'), 'yyyy')}
            </p>
          </div>

          {hasComponents && (
            <div className="flex-shrink-0 ml-2">
              {isExpanded ? (
                <ChevronUp className="h-5 w-5 text-muted-foreground" />
              ) : (
                <ChevronDown className="h-5 w-5 text-muted-foreground" />
              )}
            </div>
          )}
        </div>

        {/* Category rows */}
        <div className="mt-3 space-y-2">
          {Array.from(byCategory.entries()).map(
            ([category, categoryScores]) => {
              const config = CATEGORY_CONFIG[category];
              const Icon = config?.icon || Activity;
              return (
                <div key={category} className="flex items-center gap-3">
                  <div className="flex items-center gap-2 w-28 flex-shrink-0">
                    <Icon
                      className={`h-3.5 w-3.5 ${config?.color || 'text-muted-foreground'}`}
                    />
                    <span className="text-xs text-muted-foreground">
                      {config?.label || category}
                    </span>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    {categoryScores.map((score) => {
                      const resilienceScore =
                        category === 'resilience'
                          ? (score.components?.resilience_score?.value ?? null)
                          : null;
                      return (
                        <div
                          key={score.id}
                          className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-muted/50 border border-border/30"
                        >
                          <SourceBadge provider={score.provider || 'unknown'} />
                          <span className="text-sm font-semibold text-foreground">
                            {resilienceScore !== null
                              ? Number(resilienceScore).toFixed(0)
                              : formatScore(score.value, category)}
                          </span>
                          {resilienceScore !== null && (
                            <span className="text-[10px] text-muted-foreground">
                              {formatScore(score.value, 'resilience')}
                            </span>
                          )}
                          {score.qualifier && (
                            <span className="text-[10px] text-muted-foreground uppercase tracking-wide">
                              {score.qualifier}
                            </span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            }
          )}
        </div>
      </button>

      {/* Expanded: show components */}
      {isExpanded && (
        <div className="px-4 pb-4 pt-2 border-t border-border/60">
          <h4 className="text-xs font-medium text-muted-foreground mb-3 uppercase tracking-wider">
            Score Components
          </h4>
          <div className="space-y-4">
            {scores
              .filter(
                (s) => s.components && Object.keys(s.components).length > 0
              )
              .map((score) => (
                <div key={score.id}>
                  <div className="flex items-center gap-2 mb-2">
                    <SourceBadge provider={score.provider || 'unknown'} />
                    <span className="text-xs text-muted-foreground">
                      {CATEGORY_CONFIG[score.category]?.label || score.category}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-1 pl-4">
                    {Object.entries(score.components!).map(([key, comp]) => (
                      <div
                        key={key}
                        className="flex items-center justify-between py-1"
                      >
                        <span className="text-xs text-muted-foreground">
                          {formatComponentName(key)}
                        </span>
                        <div className="flex items-center gap-1.5">
                          <span className="text-xs font-medium text-foreground">
                            {formatScore(comp.value)}
                          </span>
                          {comp.qualifier && (
                            <span className="text-[10px] text-muted-foreground/70 uppercase">
                              {comp.qualifier}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ScoresSkeleton() {
  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="h-7 w-20 bg-muted rounded-full animate-pulse"
          />
        ))}
      </div>
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="p-4 border border-border/60 rounded-lg bg-card/30"
          >
            <div className="h-5 w-24 bg-muted rounded animate-pulse mb-3" />
            <div className="space-y-2">
              <div className="flex gap-2">
                <div className="h-8 w-32 bg-muted rounded animate-pulse" />
                <div className="h-8 w-32 bg-muted rounded animate-pulse" />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface ScoresSectionProps {
  userId: string;
  dateRange: DateRangeValue;
  onDateRangeChange: (value: DateRangeValue) => void;
}

export function ScoresSection({
  userId,
  dateRange,
  onDateRangeChange,
}: ScoresSectionProps) {
  const { startDate, endDate } = useDateRange(dateRange);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');

  const { data: scoresData, isLoading } = useHealthScores(userId, {
    start_date: startDate,
    end_date: endDate,
    limit: 1000,
  });

  const scores = useMemo(() => scoresData?.data ?? [], [scoresData?.data]);

  // Categories that have data, in defined order
  const availableCategories = useMemo(() => {
    const cats = new Set(scores.map((s) => s.category));
    return CATEGORY_ORDER.filter((c) => cats.has(c));
  }, [scores]);

  // Reset category when it's no longer available in the current data
  useEffect(() => {
    if (
      selectedCategory !== 'all' &&
      availableCategories.length > 0 &&
      !availableCategories.includes(selectedCategory)
    ) {
      setSelectedCategory('all');
    }
  }, [availableCategories, selectedCategory]);

  // Unique providers for the selected category
  const providers = useMemo(() => {
    const filtered =
      selectedCategory === 'all'
        ? scores
        : scores.filter((s) => s.category === selectedCategory);
    return [
      ...new Set(filtered.map((s) => s.provider).filter(Boolean)),
    ] as string[];
  }, [scores, selectedCategory]);

  // Chart data (only for a specific category)
  const chartData = useMemo(() => {
    if (selectedCategory === 'all') return [];
    return buildChartData(scores, selectedCategory);
  }, [scores, selectedCategory]);

  // Daily scores grouped by date
  const dailyScores = useMemo(() => {
    const filtered =
      selectedCategory === 'all'
        ? scores
        : scores.filter((s) => s.category === selectedCategory);

    const byDate = groupScoresByDate(filtered);

    return Array.from(byDate.entries())
      .sort((a, b) => b[0].localeCompare(a[0]))
      .map(([date, dayScores]) => ({ date, scores: dayScores }));
  }, [scores, selectedCategory]);

  const categoryConfig = CATEGORY_CONFIG[selectedCategory];

  return (
    <div className="space-y-6">
      {/* Summary + Chart Section */}
      <div className="rounded-2xl border border-border/60 bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-xl overflow-hidden">
        <SectionHeader
          title="Health Scores"
          dateRange={dateRange}
          onDateRangeChange={onDateRangeChange}
        />

        <div className="px-6 pt-4">
          <p className="text-xs text-yellow-300/90 bg-yellow-500/10 border border-yellow-500/20 rounded-md px-3 py-2">
            Scores calculated by Open Wearables (OW) are in an experimental
            phase and may change as the algorithm is refined.
          </p>
        </div>

        <div className="p-6">
          {isLoading ? (
            <ScoresSkeleton />
          ) : scores.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">
              No health scores in this period
            </p>
          ) : (
            <div className="space-y-6">
              {/* Category filter pills */}
              <div className="flex flex-wrap gap-2">
                <CategoryPill
                  label="All"
                  isSelected={selectedCategory === 'all'}
                  onClick={() => setSelectedCategory('all')}
                />
                {availableCategories.map((cat) => {
                  const config = CATEGORY_CONFIG[cat];
                  return (
                    <CategoryPill
                      key={cat}
                      label={config?.label || cat}
                      icon={config?.icon}
                      iconColor={config?.color}
                      isSelected={selectedCategory === cat}
                      onClick={() => setSelectedCategory(cat)}
                    />
                  );
                })}
              </div>

              {/* Provider comparison chart */}
              {selectedCategory !== 'all' &&
                chartData.length > 1 &&
                providers.length > 0 && (
                  <div className="pt-4 border-t border-border/60">
                    <div className="flex items-center justify-between mb-4">
                      <h4 className="text-sm font-medium text-foreground">
                        {categoryConfig?.label || selectedCategory} Score Trend
                      </h4>
                      <div className="flex items-center gap-3">
                        {providers.map((provider) => (
                          <div
                            key={provider}
                            className="flex items-center gap-1.5"
                          >
                            <div
                              className="w-2.5 h-2.5 rounded-full"
                              style={{
                                backgroundColor: getProviderColor(provider),
                              }}
                            />
                            <span className="text-xs text-muted-foreground">
                              {getProviderLabel(provider)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                    <ChartContainer
                      config={Object.fromEntries(
                        providers.map((p) => [
                          p,
                          {
                            label: getProviderLabel(p),
                            color: getProviderColor(p),
                          },
                        ])
                      )}
                      className="h-[200px] w-full"
                    >
                      <LineChart accessibilityLayer data={chartData}>
                        <CartesianGrid vertical={false} strokeDasharray="3 3" />
                        <XAxis
                          dataKey="date"
                          tickLine={false}
                          axisLine={false}
                          tickMargin={8}
                          interval="preserveStartEnd"
                          tick={{ fill: '#71717a', fontSize: 11 }}
                        />
                        <YAxis
                          tickLine={false}
                          axisLine={false}
                          tickMargin={8}
                          tick={{ fill: '#71717a', fontSize: 11 }}
                          domain={[0, categoryConfig?.maxScale || 100]}
                          width={selectedCategory === 'resilience' ? 45 : 35}
                          tickFormatter={
                            selectedCategory === 'resilience'
                              ? (v) => `${v}%`
                              : undefined
                          }
                        />
                        <ChartTooltip
                          cursor={false}
                          content={
                            <ChartTooltipContent
                              formatter={
                                selectedCategory === 'resilience'
                                  ? (value) => `${Number(value).toFixed(1)}%`
                                  : undefined
                              }
                            />
                          }
                        />
                        {providers.map((provider) => (
                          <Line
                            key={provider}
                            dataKey={provider}
                            type="monotone"
                            stroke={`var(--color-${provider})`}
                            strokeWidth={2}
                            dot={false}
                            activeDot={{
                              r: 4,
                              fill: `var(--color-${provider})`,
                            }}
                            connectNulls
                          />
                        ))}
                      </LineChart>
                    </ChartContainer>
                  </div>
                )}
            </div>
          )}
        </div>
      </div>

      {/* Daily Scores */}
      {!isLoading && dailyScores.length > 0 && (
        <div className="rounded-2xl border border-border/60 bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-xl overflow-hidden">
          <SectionHeader title="Daily Scores" />
          <div className="p-6">
            <div className="space-y-3">
              {dailyScores.map(({ date, scores: dayScores }) => (
                <ScoreDayCard key={date} date={date} scores={dayScores} />
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

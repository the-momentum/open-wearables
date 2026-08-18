import { SourceBadge } from '@/components/common/source-badge';
import type { CoverageResponse } from '@/lib/api';

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-center">
      <div
        className={
          value === 0
            ? 'text-lg font-semibold tabular-nums text-zinc-600'
            : 'text-lg font-semibold tabular-nums text-emerald-400'
        }
      >
        {value}
      </div>
      <div className="text-[10px] uppercase tracking-wide text-zinc-500">
        {label}
      </div>
    </div>
  );
}

interface Chip {
  code: string;
  unit?: string;
}

function GroupCard({ title, chips }: { title: string; chips: Chip[] }) {
  return (
    <div className="space-y-2.5 rounded-lg border border-zinc-800 bg-zinc-950/40 p-3.5">
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-xs font-medium uppercase tracking-wider text-zinc-400">
          {title}
        </h4>
        <span className="text-[10px] tabular-nums text-zinc-600">
          {chips.length}
        </span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {chips.map((c) => (
          <span
            key={c.code}
            className="inline-flex items-baseline gap-1 rounded-md bg-zinc-800/70 px-2 py-1"
          >
            <code className="font-mono text-xs text-zinc-200">{c.code}</code>
            {c.unit && <span className="text-[10px] text-zinc-500">{c.unit}</span>}
          </span>
        ))}
      </div>
    </div>
  );
}

interface Props {
  data: CoverageResponse;
  provider: string;
}

export function ProviderDetail({ data, provider }: Props) {
  const timeseries = data.timeseries
    .map((cat) => ({
      name: cat.name,
      metrics: cat.metrics.filter((m) => m.providers.includes(provider)),
    }))
    .filter((cat) => cat.metrics.length > 0);

  const tsCount = timeseries.reduce((n, c) => n + c.metrics.length, 0);
  const workout = data.workout_fields
    .filter((f) => f.providers.includes(provider))
    .map((f) => ({ code: f.code }));
  const sleep = data.sleep_fields
    .filter((f) => f.providers.includes(provider))
    .map((f) => ({ code: f.code }));
  const womensHealth = data.menstrual_cycle_fields
    .filter((f) => f.providers.includes(provider))
    .map((f) => ({ code: f.code }));
  const scores = data.health_scores
    .filter((s) => s.providers.includes(provider))
    .map((s) => ({ code: s.code }));

  // One card per non-empty group, rendered in a uniform responsive grid.
  const cards: { title: string; chips: Chip[] }[] = [
    ...timeseries.map((cat) => ({
      title: cat.name,
      chips: cat.metrics.map((m) => ({ code: m.code, unit: m.unit })),
    })),
    { title: 'Workout fields', chips: workout },
    { title: 'Sleep fields', chips: sleep },
    { title: "Women's health fields", chips: womensHealth },
    { title: 'Health scores', chips: scores },
  ].filter((c) => c.chips.length > 0);

  return (
    <div className="overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/50">
      {/* Header */}
      <div className="flex flex-col gap-4 border-b border-zinc-800/80 bg-zinc-900/60 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <SourceBadge provider={provider} />
          <span className="text-sm text-zinc-400">supported data types</span>
        </div>
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
          <Stat label="Timeseries" value={tsCount} />
          <Stat label="Workout" value={workout.length} />
          <Stat label="Sleep" value={sleep.length} />
          <Stat label="Women's Health" value={womensHealth.length} />
          <Stat label="Scores" value={scores.length} />
        </div>
      </div>

      {/* Card grid */}
      <div className="grid gap-3 p-5 sm:grid-cols-2 lg:grid-cols-3">
        {cards.map((c) => (
          <GroupCard key={c.title} title={c.title} chips={c.chips} />
        ))}
      </div>
    </div>
  );
}

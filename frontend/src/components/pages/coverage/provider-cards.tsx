import type { CoverageResponse } from '@/lib/api';

const PROVIDER_LABELS: Record<string, string> = {
  apple: 'Apple',
  samsung: 'Samsung',
  google: 'Google',
  garmin: 'Garmin',
  oura: 'Oura',
  polar: 'Polar',
  suunto: 'Suunto',
  whoop: 'Whoop',
  ultrahuman: 'Ultrahuman',
  strava: 'Strava',
  fitbit: 'Fitbit',
};

interface Stat {
  label: string;
  value: number;
  max: number;
}

function StatBar({ label, value, max }: Stat) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-zinc-500">{label}</span>
        <span className="tabular-nums text-zinc-300 font-medium">{value}</span>
      </div>
      <div className="h-1 rounded-full bg-zinc-800 overflow-hidden">
        <div
          className="h-full rounded-full bg-emerald-500/70 transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

interface Props {
  data: CoverageResponse;
}

export function ProviderCards({ data }: Props) {
  const { providers, timeseries, workout_fields, sleep_fields, health_scores } = data;

  const maxTimeseries = Math.max(
    ...providers.map((p) =>
      timeseries.flatMap((c) => c.metrics).filter((m) => m.providers.includes(p)).length
    )
  );
  const maxWorkout = workout_fields.length;
  const maxSleep = sleep_fields.length;
  const maxScores = health_scores.length;

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
      {providers.map((p) => {
        const tsCount = timeseries
          .flatMap((c) => c.metrics)
          .filter((m) => m.providers.includes(p)).length;
        const wCount = workout_fields.filter((f) => f.providers.includes(p)).length;
        const sCount = sleep_fields.filter((f) => f.providers.includes(p)).length;
        const hCount = health_scores.filter((s) => s.providers.includes(p)).length;

        return (
          <div
            key={p}
            className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4 space-y-3 hover:border-zinc-700 transition-colors"
          >
            <div className="flex items-center gap-2">
              <img
                src={`/provider-icons/${p}.svg`}
                alt={PROVIDER_LABELS[p]}
                className="h-5 w-5 object-contain opacity-80"
                onError={(e) => {
                  (e.target as HTMLImageElement).style.display = 'none';
                }}
              />
              <span className="text-sm font-semibold text-zinc-100 truncate">
                {PROVIDER_LABELS[p] ?? p}
              </span>
            </div>
            <div className="space-y-2">
              <StatBar label="Timeseries" value={tsCount} max={maxTimeseries} />
              <StatBar label="Workout" value={wCount} max={maxWorkout} />
              <StatBar label="Sleep" value={sCount} max={maxSleep} />
              <StatBar label="Scores" value={hCount} max={maxScores} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

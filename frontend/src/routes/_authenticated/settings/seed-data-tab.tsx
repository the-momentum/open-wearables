import { useMemo, useState } from 'react';
import { useSeedPresets, useGenerateSeedData } from '@/hooks/api/use-seed-data';
import type {
  SeedProfileConfig,
  SeedPreset,
} from '@/lib/api/services/seed-data.service';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import {
  Loader2,
  Dumbbell,
  Moon,
  Activity,
  Users,
  Wifi,
  Play,
  CalendarDays,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Default state
// ---------------------------------------------------------------------------

/** Format a Date as YYYY-MM-DD for <input type="date">. */
function toISODate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

/** Number of calendar days between two YYYY-MM-DD strings (inclusive). */
function daysBetween(from: string | null, to: string | null): number | null {
  if (!from || !to) return null;
  const diff = new Date(to).getTime() - new Date(from).getTime();
  return Math.floor(diff / 86_400_000) + 1;
}

const DEFAULT_DATE_FROM = toISODate(
  new Date(Date.now() - 6 * 30 * 86_400_000)
);
const DEFAULT_DATE_TO = toISODate(new Date());

const DEFAULT_PROFILE: SeedProfileConfig = {
  preset: null,
  generate_workouts: true,
  generate_sleep: true,
  generate_time_series: true,
  providers: null,
  num_connections: 2,
  workout_config: {
    count: 80,
    workout_types: null,
    duration_min_minutes: 15,
    duration_max_minutes: 180,
    hr_min_range: [90, 120],
    hr_max_range: [140, 180],
    steps_range: [500, 20000],
    time_series_chance_pct: 30,
    date_range_months: 6,
    date_from: DEFAULT_DATE_FROM,
    date_to: DEFAULT_DATE_TO,
  },
  sleep_config: {
    count: 20,
    duration_min_minutes: 300,
    duration_max_minutes: 600,
    nap_chance_pct: 10,
    weekend_catchup: false,
    date_range_months: 6,
    date_from: DEFAULT_DATE_FROM,
    date_to: DEFAULT_DATE_TO,
  },
};

// Common workout types displayed as checkboxes
const COMMON_WORKOUT_TYPES = [
  'running',
  'cycling',
  'swimming',
  'strength_training',
  'boxing',
  'soccer',
  'walking',
  'hiking',
  'yoga',
  'rowing',
] as const;

const PROVIDERS = [
  { id: 'apple', label: 'Apple Health' },
  { id: 'garmin', label: 'Garmin' },
  { id: 'polar', label: 'Polar' },
  { id: 'suunto', label: 'Suunto' },
  { id: 'whoop', label: 'WHOOP' },
] as const;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SeedDataTab() {
  const { data: presets, isLoading: presetsLoading } = useSeedPresets();
  const generateMutation = useGenerateSeedData();

  const [numUsers, setNumUsers] = useState(1);
  const [activePreset, setActivePreset] = useState<string | null>(null);
  const [profile, setProfile] = useState<SeedProfileConfig>(DEFAULT_PROFILE);

  // Apply a preset to the form, filling in date defaults for fields the preset
  // may not include (backend presets use date_range_months instead).
  const applyPreset = (preset: SeedPreset) => {
    setActivePreset(preset.id);
    setProfile({
      ...preset.profile,
      workout_config: {
        ...preset.profile.workout_config,
        date_from: preset.profile.workout_config.date_from ?? DEFAULT_DATE_FROM,
        date_to: preset.profile.workout_config.date_to ?? DEFAULT_DATE_TO,
      },
      sleep_config: {
        ...preset.profile.sleep_config,
        date_from: preset.profile.sleep_config.date_from ?? DEFAULT_DATE_FROM,
        date_to: preset.profile.sleep_config.date_to ?? DEFAULT_DATE_TO,
      },
    });
  };

  const resetToDefault = () => {
    setActivePreset(null);
    setProfile(DEFAULT_PROFILE);
  };

  const handleGenerate = () => {
    generateMutation.mutate({
      num_users: numUsers,
      profile,
    });
  };

  // Sleep count validation: cannot exceed days in the selected date range
  const sleepDays = useMemo(
    () =>
      daysBetween(
        profile.sleep_config.date_from,
        profile.sleep_config.date_to
      ),
    [profile.sleep_config.date_from, profile.sleep_config.date_to]
  );
  const sleepCountExceedsDays =
    sleepDays !== null && profile.sleep_config.count > sleepDays;

  // Workout type checkbox helpers
  const selectedWorkoutTypes = profile.workout_config.workout_types;

  const toggleWorkoutType = (type: string) => {
    const current = selectedWorkoutTypes ?? [];
    const updated = current.includes(type)
      ? current.filter((t) => t !== type)
      : [...current, type];
    setProfile({
      ...profile,
      workout_config: {
        ...profile.workout_config,
        workout_types: updated.length > 0 ? updated : null,
      },
    });
    setActivePreset(null);
  };

  // Provider checkbox helpers
  const selectedProviders = profile.providers;

  const toggleProvider = (provider: string) => {
    const current = selectedProviders ?? [];
    const updated = current.includes(provider)
      ? current.filter((p) => p !== provider)
      : [...current, provider];
    setProfile({
      ...profile,
      providers: updated.length > 0 ? updated : null,
    });
    setActivePreset(null);
  };

  return (
    <div className="space-y-8 max-w-4xl">
      {/* Header */}
      <div>
        <h2 className="text-lg font-medium text-white">Seed Data Generator</h2>
        <p className="text-sm text-zinc-500 mt-1">
          Generate synthetic users with customizable health data profiles for
          testing.
        </p>
      </div>

      {/* User count */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
        <div className="flex items-center gap-3 mb-4">
          <Users className="h-4 w-4 text-zinc-400" />
          <h3 className="text-sm font-medium text-white">Users</h3>
        </div>
        <div className="flex items-center gap-3">
          <Label htmlFor="num-users" className="text-sm text-zinc-400">
            Number of users to create
          </Label>
          <Input
            id="num-users"
            type="number"
            min={1}
            max={10}
            value={numUsers}
            onChange={(e) =>
              setNumUsers(
                Math.max(1, Math.min(10, parseInt(e.target.value) || 1))
              )
            }
            className="w-20"
          />
        </div>
      </div>

      {/* Presets */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-medium text-white">Profile Presets</h3>
          {activePreset && (
            <button
              onClick={resetToDefault}
              className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
            >
              Reset to default
            </button>
          )}
        </div>
        {presetsLoading ? (
          <div className="flex items-center gap-2 text-zinc-500 text-sm">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading presets...
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-3">
            {presets?.map((preset) => (
              <button
                key={preset.id}
                onClick={() => applyPreset(preset)}
                className={`text-left p-3 rounded-lg border transition-colors ${
                  activePreset === preset.id
                    ? 'border-blue-500/50 bg-blue-500/10'
                    : 'border-zinc-700 bg-zinc-800/50 hover:border-zinc-600'
                }`}
              >
                <div className="text-sm font-medium text-white">
                  {preset.label}
                </div>
                <div className="text-xs text-zinc-500 mt-1 line-clamp-2">
                  {preset.description}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Workouts */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <Dumbbell className="h-4 w-4 text-zinc-400" />
            <h3 className="text-sm font-medium text-white">Workouts</h3>
          </div>
          <Switch
            checked={profile.generate_workouts}
            onCheckedChange={(checked) => {
              setProfile({ ...profile, generate_workouts: checked });
              setActivePreset(null);
            }}
          />
        </div>

        {profile.generate_workouts && (
          <div className="space-y-4 pt-2">
            <div className="grid grid-cols-3 gap-4">
              <div>
                <Label className="text-xs text-zinc-500">Count</Label>
                <Input
                  type="number"
                  min={1}
                  max={500}
                  value={profile.workout_config.count}
                  onChange={(e) => {
                    setProfile({
                      ...profile,
                      workout_config: {
                        ...profile.workout_config,
                        count: parseInt(e.target.value) || 1,
                      },
                    });
                    setActivePreset(null);
                  }}
                  className="mt-1"
                />
              </div>
              <div>
                <Label className="text-xs text-zinc-500">
                  Duration min (min)
                </Label>
                <Input
                  type="number"
                  min={5}
                  max={600}
                  value={profile.workout_config.duration_min_minutes}
                  onChange={(e) => {
                    setProfile({
                      ...profile,
                      workout_config: {
                        ...profile.workout_config,
                        duration_min_minutes: parseInt(e.target.value) || 5,
                      },
                    });
                    setActivePreset(null);
                  }}
                  className="mt-1"
                />
              </div>
              <div>
                <Label className="text-xs text-zinc-500">
                  Duration max (min)
                </Label>
                <Input
                  type="number"
                  min={5}
                  max={600}
                  value={profile.workout_config.duration_max_minutes}
                  onChange={(e) => {
                    setProfile({
                      ...profile,
                      workout_config: {
                        ...profile.workout_config,
                        duration_max_minutes: parseInt(e.target.value) || 5,
                      },
                    });
                    setActivePreset(null);
                  }}
                  className="mt-1"
                />
              </div>
            </div>

            <div>
              <div className="flex items-center gap-2 mb-2">
                <CalendarDays className="h-3.5 w-3.5 text-zinc-500" />
                <Label className="text-xs text-zinc-500">Date range</Label>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label className="text-xs text-zinc-600">From</Label>
                  <Input
                    type="date"
                    value={profile.workout_config.date_from ?? ''}
                    onChange={(e) => {
                      setProfile({
                        ...profile,
                        workout_config: {
                          ...profile.workout_config,
                          date_from: e.target.value || null,
                        },
                      });
                      setActivePreset(null);
                    }}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label className="text-xs text-zinc-600">To</Label>
                  <Input
                    type="date"
                    value={profile.workout_config.date_to ?? ''}
                    onChange={(e) => {
                      setProfile({
                        ...profile,
                        workout_config: {
                          ...profile.workout_config,
                          date_to: e.target.value || null,
                        },
                      });
                      setActivePreset(null);
                    }}
                    className="mt-1"
                  />
                </div>
              </div>
            </div>

            <div>
              <Label className="text-xs text-zinc-500 mb-2 block">
                Workout types{' '}
                <span className="text-zinc-600">
                  (none selected = all types)
                </span>
              </Label>
              <div className="flex flex-wrap gap-2">
                {COMMON_WORKOUT_TYPES.map((type) => (
                  <button
                    key={type}
                    onClick={() => toggleWorkoutType(type)}
                    className={`px-3 py-1 text-xs rounded-full border transition-colors ${
                      selectedWorkoutTypes?.includes(type)
                        ? 'border-blue-500/50 bg-blue-500/15 text-blue-400'
                        : 'border-zinc-700 text-zinc-400 hover:border-zinc-600'
                    }`}
                  >
                    {type.replace(/_/g, ' ')}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Sleep */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <Moon className="h-4 w-4 text-zinc-400" />
            <h3 className="text-sm font-medium text-white">Sleep Records</h3>
          </div>
          <Switch
            checked={profile.generate_sleep}
            onCheckedChange={(checked) => {
              setProfile({ ...profile, generate_sleep: checked });
              setActivePreset(null);
            }}
          />
        </div>

        {profile.generate_sleep && (
          <div className="space-y-4 pt-2">
            <div className="grid grid-cols-3 gap-4">
              <div>
                <Label className="text-xs text-zinc-500">Count</Label>
                <Input
                  type="number"
                  min={1}
                  max={365}
                  value={profile.sleep_config.count}
                  onChange={(e) => {
                    setProfile({
                      ...profile,
                      sleep_config: {
                        ...profile.sleep_config,
                        count: parseInt(e.target.value) || 1,
                      },
                    });
                    setActivePreset(null);
                  }}
                  className="mt-1"
                />
              </div>
              <div>
                <Label className="text-xs text-zinc-500">
                  Duration min (min)
                </Label>
                <Input
                  type="number"
                  min={60}
                  max={720}
                  value={profile.sleep_config.duration_min_minutes}
                  onChange={(e) => {
                    setProfile({
                      ...profile,
                      sleep_config: {
                        ...profile.sleep_config,
                        duration_min_minutes: parseInt(e.target.value) || 60,
                      },
                    });
                    setActivePreset(null);
                  }}
                  className="mt-1"
                />
              </div>
              <div>
                <Label className="text-xs text-zinc-500">
                  Duration max (min)
                </Label>
                <Input
                  type="number"
                  min={60}
                  max={720}
                  value={profile.sleep_config.duration_max_minutes}
                  onChange={(e) => {
                    setProfile({
                      ...profile,
                      sleep_config: {
                        ...profile.sleep_config,
                        duration_max_minutes: parseInt(e.target.value) || 60,
                      },
                    });
                    setActivePreset(null);
                  }}
                  className="mt-1"
                />
              </div>
            </div>

            <div>
              <div className="flex items-center gap-2 mb-2">
                <CalendarDays className="h-3.5 w-3.5 text-zinc-500" />
                <Label className="text-xs text-zinc-500">Date range</Label>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label className="text-xs text-zinc-600">From</Label>
                  <Input
                    type="date"
                    value={profile.sleep_config.date_from ?? ''}
                    onChange={(e) => {
                      setProfile({
                        ...profile,
                        sleep_config: {
                          ...profile.sleep_config,
                          date_from: e.target.value || null,
                        },
                      });
                      setActivePreset(null);
                    }}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label className="text-xs text-zinc-600">To</Label>
                  <Input
                    type="date"
                    value={profile.sleep_config.date_to ?? ''}
                    onChange={(e) => {
                      setProfile({
                        ...profile,
                        sleep_config: {
                          ...profile.sleep_config,
                          date_to: e.target.value || null,
                        },
                      });
                      setActivePreset(null);
                    }}
                    className="mt-1"
                  />
                </div>
              </div>
              {sleepCountExceedsDays && (
                <p className="text-xs text-red-400 mt-2">
                  Sleep count ({profile.sleep_config.count}) exceeds the number
                  of days in the selected range ({sleepDays}). Each day can have
                  at most one sleep record.
                </p>
              )}
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-xs text-zinc-500">Nap chance (%)</Label>
                <Input
                  type="number"
                  min={0}
                  max={100}
                  value={profile.sleep_config.nap_chance_pct}
                  onChange={(e) => {
                    setProfile({
                      ...profile,
                      sleep_config: {
                        ...profile.sleep_config,
                        nap_chance_pct: parseInt(e.target.value) || 0,
                      },
                    });
                    setActivePreset(null);
                  }}
                  className="mt-1"
                />
              </div>
              <div className="flex items-end gap-3 pb-1">
                <Switch
                  id="weekend-catchup"
                  checked={profile.sleep_config.weekend_catchup}
                  onCheckedChange={(checked) => {
                    setProfile({
                      ...profile,
                      sleep_config: {
                        ...profile.sleep_config,
                        weekend_catchup: checked,
                      },
                    });
                    setActivePreset(null);
                  }}
                />
                <Label
                  htmlFor="weekend-catchup"
                  className="text-sm text-zinc-400"
                >
                  Weekend catch-up
                  <span className="block text-xs text-zinc-600">
                    Short weekday sleep, long weekend sleep
                  </span>
                </Label>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Time Series */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Activity className="h-4 w-4 text-zinc-400" />
            <h3 className="text-sm font-medium text-white">Time Series</h3>
          </div>
          <Switch
            checked={profile.generate_time_series}
            onCheckedChange={(checked) => {
              setProfile({ ...profile, generate_time_series: checked });
              setActivePreset(null);
            }}
          />
        </div>
        {profile.generate_time_series && profile.generate_workouts && (
          <div className="mt-4">
            <Label className="text-xs text-zinc-500">
              Chance per workout (%)
            </Label>
            <Input
              type="number"
              min={0}
              max={100}
              value={profile.workout_config.time_series_chance_pct}
              onChange={(e) => {
                setProfile({
                  ...profile,
                  workout_config: {
                    ...profile.workout_config,
                    time_series_chance_pct: parseInt(e.target.value) || 0,
                  },
                });
                setActivePreset(null);
              }}
              className="mt-1 w-24"
            />
          </div>
        )}
        {profile.generate_time_series && !profile.generate_workouts && (
          <p className="text-xs text-zinc-600 mt-3">
            Time series data requires workouts to be enabled.
          </p>
        )}
      </div>

      {/* Providers */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
        <div className="flex items-center gap-3 mb-4">
          <Wifi className="h-4 w-4 text-zinc-400" />
          <h3 className="text-sm font-medium text-white">Providers</h3>
          <span className="text-xs text-zinc-600">
            (none selected = random {profile.num_connections})
          </span>
        </div>
        <div className="flex flex-wrap gap-2 mb-4">
          {PROVIDERS.map((prov) => (
            <button
              key={prov.id}
              onClick={() => toggleProvider(prov.id)}
              className={`px-3 py-1 text-xs rounded-full border transition-colors ${
                selectedProviders?.includes(prov.id)
                  ? 'border-blue-500/50 bg-blue-500/15 text-blue-400'
                  : 'border-zinc-700 text-zinc-400 hover:border-zinc-600'
              }`}
            >
              {prov.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-3">
          <Label className="text-xs text-zinc-500">Connections per user</Label>
          <Input
            type="number"
            min={1}
            max={5}
            value={profile.num_connections}
            onChange={(e) => {
              setProfile({
                ...profile,
                num_connections: Math.max(
                  1,
                  Math.min(5, parseInt(e.target.value) || 1)
                ),
              });
              setActivePreset(null);
            }}
            className="w-20"
          />
        </div>
      </div>

      {/* Generate button */}
      <div className="flex items-center gap-4">
        <Button
          onClick={handleGenerate}
          disabled={generateMutation.isPending || sleepCountExceedsDays}
          className="gap-2"
        >
          {generateMutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Play className="h-4 w-4" />
          )}
          {generateMutation.isPending
            ? 'Dispatching...'
            : `Generate ${numUsers} user${numUsers > 1 ? 's' : ''}`}
        </Button>
        <span className="text-xs text-zinc-600">
          Data generation runs in the background via Celery.
        </span>
      </div>
    </div>
  );
}

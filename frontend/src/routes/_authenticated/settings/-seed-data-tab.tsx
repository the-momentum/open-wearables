import { useMemo, useState } from 'react';
import {
  useSeedPresets,
  useGenerateSeedData,
  useSleepStageProfiles,
} from '@/hooks/api/use-seed-data';
import type {
  SeedProfileConfig,
  SeedPreset,
  SleepStageDistribution,
  SleepStageProfile,
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

/** Format a Date as YYYY-MM-DD in local time for <input type="date">. */
function toISODate(d: Date): string {
  const offset = d.getTimezoneOffset() * 60_000;
  return new Date(d.getTime() - offset).toISOString().slice(0, 10);
}

/** Number of calendar days between two YYYY-MM-DD strings (inclusive). */
function daysBetween(from: string | null, to: string | null): number | null {
  if (!from || !to) return null;
  const diff = new Date(to).getTime() - new Date(from).getTime();
  return Math.floor(diff / 86_400_000) + 1;
}

const DEFAULT_DATE_FROM = toISODate(new Date(Date.now() - 6 * 30 * 86_400_000));
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
    stage_profile: null,
    stage_distribution: {
      deep_pct_range: [15, 25],
      rem_pct_range: [20, 25],
      awake_pct_range: [2, 8],
    },
  },
  time_series_config: {
    enabled_types: [],
    include_blood_pressure: false,
    date_range_months: 6,
    date_from: DEFAULT_DATE_FROM,
    date_to: DEFAULT_DATE_TO,
  },
};

// Curated list of the 20-30 most common continuous series types, grouped
// semantically. Paired blood_pressure is rendered as a single toggle below.
const CONTINUOUS_SERIES_GROUPS: {
  label: string;
  types: { id: string; label: string }[];
}[] = [
  {
    label: 'Heart & cardiovascular',
    types: [
      { id: 'heart_rate', label: 'Heart rate' },
      { id: 'resting_heart_rate', label: 'Resting heart rate' },
      { id: 'heart_rate_variability_sdnn', label: 'HRV (SDNN)' },
    ],
  },
  {
    label: 'Blood & respiratory',
    types: [
      { id: 'respiratory_rate', label: 'Respiratory rate' },
      { id: 'oxygen_saturation', label: 'Oxygen saturation' },
      { id: 'blood_glucose', label: 'Blood glucose' },
    ],
  },
  {
    label: 'Body',
    types: [
      { id: 'weight', label: 'Weight' },
      { id: 'body_fat_percentage', label: 'Body fat %' },
      { id: 'body_temperature', label: 'Body temperature' },
      { id: 'skin_temperature', label: 'Skin temperature' },
      { id: 'vo2_max', label: 'VO₂ max' },
    ],
  },
  {
    label: 'Activity',
    types: [
      { id: 'steps', label: 'Steps' },
      { id: 'energy', label: 'Energy burned' },
      { id: 'basal_energy', label: 'Basal energy' },
      { id: 'distance_walking_running', label: 'Distance (walk/run)' },
      { id: 'flights_climbed', label: 'Flights climbed' },
      { id: 'stand_time', label: 'Stand time' },
      { id: 'exercise_time', label: 'Exercise time' },
    ],
  },
  {
    label: 'Environmental',
    types: [
      { id: 'time_in_daylight', label: 'Time in daylight' },
      { id: 'environmental_audio_exposure', label: 'Environmental audio' },
      { id: 'headphone_audio_exposure', label: 'Headphone audio' },
    ],
  },
  {
    label: 'During workouts only',
    types: [
      { id: 'running_power', label: 'Running power' },
      { id: 'running_speed', label: 'Running speed' },
      { id: 'cadence', label: 'Cadence' },
      { id: 'power', label: 'Power' },
      { id: 'swimming_stroke_count', label: 'Swim stroke count' },
    ],
  },
];

const DEFAULT_STAGE_DISTRIBUTION: SleepStageDistribution = {
  deep_pct_range: [15, 25],
  rem_pct_range: [20, 25],
  awake_pct_range: [2, 8],
};

const STAGE_COLORS = {
  deep: 'bg-indigo-500',
  rem: 'bg-cyan-500',
  awake: 'bg-amber-500',
  light: 'bg-zinc-600',
} as const;

// Workout types grouped for the seed form. Mirrors the categories in
// backend/app/schemas/enums/workout_types.py (some niche types omitted).
const WORKOUT_TYPE_GROUPS: { label: string; types: string[] }[] = [
  {
    label: 'Running & walking',
    types: [
      'running',
      'trail_running',
      'treadmill',
      'walking',
      'walking_fitness',
      'hiking',
      'trail_hiking',
      'mountaineering',
    ],
  },
  {
    label: 'Cycling',
    types: [
      'cycling',
      'indoor_cycling',
      'mountain_biking',
      'cyclocross',
      'e_biking',
    ],
  },
  {
    label: 'Swimming & water',
    types: [
      'swimming',
      'pool_swimming',
      'open_water_swimming',
      'rowing',
      'kayaking',
      'canoeing',
      'paddling',
      'stand_up_paddleboarding',
      'surfing',
    ],
  },
  {
    label: 'Gym & fitness',
    types: [
      'strength_training',
      'cardio_training',
      'fitness_equipment',
      'elliptical',
      'rowing_machine',
      'stair_climbing',
    ],
  },
  {
    label: 'Mind & body',
    types: ['yoga', 'pilates', 'stretching', 'meditation'],
  },
  {
    label: 'Winter',
    types: [
      'cross_country_skiing',
      'alpine_skiing',
      'backcountry_skiing',
      'downhill_skiing',
      'snowboarding',
      'snowshoeing',
      'ice_skating',
    ],
  },
  {
    label: 'Team sports',
    types: [
      'soccer',
      'basketball',
      'football',
      'american_football',
      'baseball',
      'volleyball',
      'handball',
      'rugby',
      'hockey',
    ],
  },
  {
    label: 'Racket sports',
    types: [
      'tennis',
      'badminton',
      'squash',
      'table_tennis',
      'padel',
      'pickleball',
    ],
  },
  {
    label: 'Combat & climbing',
    types: [
      'boxing',
      'martial_arts',
      'wrestling',
      'rock_climbing',
      'indoor_climbing',
      'bouldering',
    ],
  },
  {
    label: 'Multisport & other',
    types: [
      'triathlon',
      'multisport',
      'dance',
      'aerobics',
      'skating',
      'inline_skating',
      'skateboarding',
      'horseback_riding',
      'golf',
    ],
  },
];

const PROVIDERS = [
  { id: 'apple', label: 'Apple Health' },
  { id: 'garmin', label: 'Garmin' },
  { id: 'oura', label: 'Oura' },
  { id: 'polar', label: 'Polar' },
  { id: 'suunto', label: 'Suunto' },
  { id: 'whoop', label: 'WHOOP' },
] as const;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SeedDataTab() {
  const { data: presets, isLoading: presetsLoading } = useSeedPresets();
  const { data: sleepStageProfiles } = useSleepStageProfiles();
  const generateMutation = useGenerateSeedData();

  const [numUsers, setNumUsers] = useState(1);
  const [randomSeed, setRandomSeed] = useState('');
  const [lastSeedUsed, setLastSeedUsed] = useState<number | null>(null);
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
        stage_profile: preset.profile.sleep_config.stage_profile ?? null,
        stage_distribution:
          preset.profile.sleep_config.stage_distribution ??
          DEFAULT_STAGE_DISTRIBUTION,
      },
      time_series_config: {
        ...(preset.profile.time_series_config ??
          DEFAULT_PROFILE.time_series_config),
        date_from:
          preset.profile.time_series_config?.date_from ?? DEFAULT_DATE_FROM,
        date_to: preset.profile.time_series_config?.date_to ?? DEFAULT_DATE_TO,
      },
    });
  };

  const clearPreset = () => {
    setActivePreset(null);
    setProfile((prev) => (prev.preset ? { ...prev, preset: null } : prev));
  };

  const resetToDefault = () => {
    setActivePreset(null);
    setProfile(DEFAULT_PROFILE);
  };

  const handleGenerate = () => {
    const parsedSeed = randomSeed !== '' ? parseInt(randomSeed) : null;
    generateMutation.mutate(
      {
        num_users: numUsers,
        profile,
        random_seed:
          parsedSeed !== null && !isNaN(parsedSeed) ? parsedSeed : null,
      },
      {
        onSuccess: (result) => {
          if (result.seed_used != null) {
            setLastSeedUsed(result.seed_used);
          }
        },
      }
    );
  };

  // Sleep count validation: cannot exceed days in the selected date range
  const sleepDays = useMemo(
    () =>
      daysBetween(profile.sleep_config.date_from, profile.sleep_config.date_to),
    [profile.sleep_config.date_from, profile.sleep_config.date_to]
  );
  const sleepCountExceedsDays =
    sleepDays !== null && profile.sleep_config.count > sleepDays;

  // Stage distribution validation
  const dist = profile.sleep_config.stage_distribution;
  const stageMaxSum =
    dist.deep_pct_range[1] + dist.rem_pct_range[1] + dist.awake_pct_range[1];
  const stageDistInvalid = stageMaxSum > 95;

  // Computed light sleep range (remainder)
  const lightMin = Math.max(
    0,
    100 -
      dist.deep_pct_range[1] -
      dist.rem_pct_range[1] -
      dist.awake_pct_range[1]
  );
  const lightMax = Math.max(
    0,
    100 -
      dist.deep_pct_range[0] -
      dist.rem_pct_range[0] -
      dist.awake_pct_range[0]
  );

  // Stacked bar midpoints for preview
  const deepMid = (dist.deep_pct_range[0] + dist.deep_pct_range[1]) / 2;
  const remMid = (dist.rem_pct_range[0] + dist.rem_pct_range[1]) / 2;
  const awakeMid = (dist.awake_pct_range[0] + dist.awake_pct_range[1]) / 2;
  const lightMid = Math.max(0, 100 - deepMid - remMid - awakeMid);

  // Apply a sleep stage profile
  const applySleepStageProfile = (p: SleepStageProfile) => {
    setProfile({
      ...profile,
      sleep_config: {
        ...profile.sleep_config,
        stage_profile: p.id,
        stage_distribution: { ...p.distribution },
      },
    });
    clearPreset();
  };

  const updateStageDistribution = (
    partial: Partial<SleepStageDistribution>
  ) => {
    setProfile({
      ...profile,
      sleep_config: {
        ...profile.sleep_config,
        stage_profile: null,
        stage_distribution: {
          ...profile.sleep_config.stage_distribution,
          ...partial,
        },
      },
    });
    clearPreset();
  };

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
    clearPreset();
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
    clearPreset();
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

      {/* User count & seed */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
        <div className="flex items-center gap-3 mb-4">
          <Users className="h-4 w-4 text-zinc-400" />
          <h3 className="text-sm font-medium text-white">Users</h3>
        </div>
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
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
          <div className="space-y-1.5">
            <div className="flex items-center gap-3">
              <Label className="text-sm text-zinc-400 whitespace-nowrap">
                Override random seed
              </Label>
              <Input
                type="number"
                placeholder="Auto-generated"
                value={randomSeed}
                onChange={(e) => setRandomSeed(e.target.value)}
                className="w-48"
              />
              {lastSeedUsed != null && (
                <button
                  onClick={() => setRandomSeed(String(lastSeedUsed))}
                  className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors whitespace-nowrap"
                >
                  Reuse last: {lastSeedUsed}
                </button>
              )}
            </div>
            <p className="text-xs text-zinc-600">
              Seed and preset are embedded in generated user names - copy the
              seed from there to reproduce data.
            </p>
          </div>
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
              clearPreset();
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
                    clearPreset();
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
                    clearPreset();
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
                    clearPreset();
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
                      clearPreset();
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
                      clearPreset();
                    }}
                    className="mt-1"
                  />
                </div>
              </div>
            </div>

            <div className="space-y-3">
              <Label className="text-xs text-zinc-500 block">
                Workout types{' '}
                <span className="text-zinc-600">
                  (none selected = all types)
                </span>
              </Label>
              {WORKOUT_TYPE_GROUPS.map((group) => (
                <div key={group.label}>
                  <div className="text-xs text-zinc-600 mb-1.5 uppercase tracking-wide">
                    {group.label}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {group.types.map((type) => (
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
              ))}
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
              clearPreset();
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
                    clearPreset();
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
                    clearPreset();
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
                    clearPreset();
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
                      clearPreset();
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
                      clearPreset();
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
                    clearPreset();
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
                    clearPreset();
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

            {/* Stage Distribution */}
            <div className="border-t border-zinc-800 pt-4 mt-2">
              <Label className="text-xs text-zinc-500 mb-3 block">
                Stage Distribution
              </Label>

              {/* Profile pills */}
              <div className="flex flex-wrap gap-2 mb-4">
                {sleepStageProfiles?.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => applySleepStageProfile(p)}
                    className={`px-3 py-1 text-xs rounded-full border transition-colors ${
                      profile.sleep_config.stage_profile === p.id
                        ? 'border-blue-500/50 bg-blue-500/15 text-blue-400'
                        : 'border-zinc-700 text-zinc-400 hover:border-zinc-600'
                    }`}
                  >
                    {p.label}
                  </button>
                ))}
              </div>

              {/* Stage percentage inputs */}
              <div className="space-y-2">
                <div className="grid grid-cols-[auto_1fr_80px_80px] items-center gap-3">
                  <span className="h-2.5 w-2.5" />
                  <span />
                  <span className="text-[10px] text-zinc-600 text-center">
                    Min %
                  </span>
                  <span className="text-[10px] text-zinc-600 text-center">
                    Max %
                  </span>
                </div>
                {(
                  [
                    ['deep', 'Deep', 'deep_pct_range'],
                    ['rem', 'REM', 'rem_pct_range'],
                    ['awake', 'Awake', 'awake_pct_range'],
                  ] as const
                ).map(([key, label, field]) => (
                  <div
                    key={key}
                    className="grid grid-cols-[auto_1fr_80px_80px] items-center gap-3"
                  >
                    <span
                      className={`h-2.5 w-2.5 rounded-full ${STAGE_COLORS[key]}`}
                    />
                    <span className="text-xs text-zinc-400">{label}</span>
                    <Input
                      type="number"
                      min={0}
                      max={95}
                      value={dist[field][0]}
                      onChange={(e) => {
                        const v = Math.max(
                          0,
                          Math.min(95, parseInt(e.target.value) || 0)
                        );
                        updateStageDistribution({
                          [field]: [v, Math.max(v, dist[field][1])],
                        } as Partial<SleepStageDistribution>);
                      }}
                      className="h-8 text-xs"
                    />
                    <Input
                      type="number"
                      min={0}
                      max={95}
                      value={dist[field][1]}
                      onChange={(e) => {
                        const v = Math.max(
                          0,
                          Math.min(95, parseInt(e.target.value) || 0)
                        );
                        updateStageDistribution({
                          [field]: [Math.min(v, dist[field][0]), v],
                        } as Partial<SleepStageDistribution>);
                      }}
                      className="h-8 text-xs"
                    />
                  </div>
                ))}
                {/* Light (calculated) */}
                <div className="grid grid-cols-[auto_1fr_80px_80px] items-center gap-3">
                  <span
                    className={`h-2.5 w-2.5 rounded-full ${STAGE_COLORS.light}`}
                  />
                  <span className="text-xs text-zinc-500">Light</span>
                  <span className="text-xs text-zinc-600 text-center">
                    ~{lightMin}%
                  </span>
                  <span className="text-xs text-zinc-600 text-center">
                    ~{lightMax}%
                  </span>
                </div>
              </div>

              {/* Stacked bar preview */}
              <div className="flex h-3 rounded-full overflow-hidden mt-3">
                <div
                  className={`${STAGE_COLORS.deep} transition-all`}
                  style={{ width: `${deepMid}%` }}
                />
                <div
                  className={`${STAGE_COLORS.rem} transition-all`}
                  style={{ width: `${remMid}%` }}
                />
                <div
                  className={`${STAGE_COLORS.light} transition-all`}
                  style={{ width: `${lightMid}%` }}
                />
                <div
                  className={`${STAGE_COLORS.awake} transition-all`}
                  style={{ width: `${awakeMid}%` }}
                />
              </div>
              <div className="flex justify-between text-[10px] text-zinc-600 mt-1">
                <span>Deep {Math.round(deepMid)}%</span>
                <span>REM {Math.round(remMid)}%</span>
                <span>Light {Math.round(lightMid)}%</span>
                <span>Awake {Math.round(awakeMid)}%</span>
              </div>

              {stageDistInvalid && (
                <p className="text-xs text-red-400 mt-2">
                  Sum of max percentages ({stageMaxSum}%) exceeds 95% - not
                  enough room for light sleep.
                </p>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Time Series */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <Activity className="h-4 w-4 text-zinc-400" />
            <h3 className="text-sm font-medium text-white">Time Series</h3>
          </div>
          <Switch
            checked={profile.generate_time_series}
            onCheckedChange={(checked) => {
              setProfile({ ...profile, generate_time_series: checked });
              clearPreset();
            }}
          />
        </div>

        {profile.generate_time_series && (
          <div className="space-y-5">
            <p className="text-xs text-zinc-500">
              Continuous samples are emitted across the date range below,
              independently of workouts. Workout-specific metrics (running
              power, cadence, ...) still come from the workout generator.
            </p>

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
                    value={profile.time_series_config.date_from ?? ''}
                    onChange={(e) => {
                      setProfile({
                        ...profile,
                        time_series_config: {
                          ...profile.time_series_config,
                          date_from: e.target.value || null,
                        },
                      });
                      clearPreset();
                    }}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label className="text-xs text-zinc-600">To</Label>
                  <Input
                    type="date"
                    value={profile.time_series_config.date_to ?? ''}
                    onChange={(e) => {
                      setProfile({
                        ...profile,
                        time_series_config: {
                          ...profile.time_series_config,
                          date_to: e.target.value || null,
                        },
                      });
                      clearPreset();
                    }}
                    className="mt-1"
                  />
                </div>
              </div>
            </div>

            <div className="space-y-4">
              {(() => {
                const allTypeIds = CONTINUOUS_SERIES_GROUPS.flatMap((g) =>
                  g.types.map((t) => t.id)
                );
                const enabled = profile.time_series_config.enabled_types;
                const allEnabled =
                  allTypeIds.every((id) => enabled.includes(id)) &&
                  profile.time_series_config.include_blood_pressure;
                return (
                  <div className="flex items-center justify-between">
                    <Label className="text-xs text-zinc-500">
                      Series types
                    </Label>
                    <button
                      onClick={() => {
                        setProfile({
                          ...profile,
                          time_series_config: {
                            ...profile.time_series_config,
                            enabled_types: allEnabled ? [] : allTypeIds,
                            include_blood_pressure: !allEnabled,
                          },
                        });
                        clearPreset();
                      }}
                      className="text-xs text-zinc-500 hover:text-zinc-300"
                    >
                      {allEnabled ? 'Clear all' : 'Select all'}
                    </button>
                  </div>
                );
              })()}
              {CONTINUOUS_SERIES_GROUPS.map((group) => (
                <div key={group.label}>
                  <div className="text-xs text-zinc-600 mb-1.5 uppercase tracking-wide">
                    {group.label}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {group.types.map((type) => {
                      const enabled = profile.time_series_config.enabled_types;
                      const selected = enabled.includes(type.id);
                      return (
                        <button
                          key={type.id}
                          onClick={() => {
                            const updated = selected
                              ? enabled.filter((t) => t !== type.id)
                              : [...enabled, type.id];
                            setProfile({
                              ...profile,
                              time_series_config: {
                                ...profile.time_series_config,
                                enabled_types: updated,
                              },
                            });
                            clearPreset();
                          }}
                          className={`px-3 py-1 text-xs rounded-full border transition-colors ${
                            selected
                              ? 'border-blue-500/50 bg-blue-500/15 text-blue-400'
                              : 'border-zinc-700 text-zinc-400 hover:border-zinc-600'
                          }`}
                        >
                          {type.label}
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}

              <div>
                <div className="text-xs text-zinc-600 mb-1.5 uppercase tracking-wide">
                  Paired
                </div>
                <button
                  onClick={() => {
                    setProfile({
                      ...profile,
                      time_series_config: {
                        ...profile.time_series_config,
                        include_blood_pressure:
                          !profile.time_series_config.include_blood_pressure,
                      },
                    });
                    clearPreset();
                  }}
                  className={`px-3 py-1 text-xs rounded-full border transition-colors ${
                    profile.time_series_config.include_blood_pressure
                      ? 'border-blue-500/50 bg-blue-500/15 text-blue-400'
                      : 'border-zinc-700 text-zinc-400 hover:border-zinc-600'
                  }`}
                >
                  Blood pressure (systolic + diastolic)
                </button>
              </div>
            </div>
          </div>
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
              clearPreset();
            }}
            className="w-20"
          />
        </div>
      </div>

      {/* Generate */}
      <div className="space-y-3">
        <div className="flex items-center gap-4">
          <Button
            onClick={handleGenerate}
            disabled={
              generateMutation.isPending ||
              sleepCountExceedsDays ||
              stageDistInvalid
            }
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
    </div>
  );
}

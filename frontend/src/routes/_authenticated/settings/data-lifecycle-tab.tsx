import { useState, useEffect, useMemo } from 'react';
import {
  useArchivalSettings,
  useUpdateArchivalSettings,
  useTriggerArchival,
} from '@/hooks/api/use-archival';
import {
  Loader2,
  CheckCircle2,
  Archive,
  Trash2,
  HardDrive,
  Play,
  AlertTriangle,
  TrendingUp,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  XAxis,
  YAxis,
  Tooltip,
} from 'recharts';
import type { StorageEstimate } from '@/lib/api/services/archival.service';

export function DataLifecycleTab() {
  const { data, isLoading, error, refetch } = useArchivalSettings();
  const updateMutation = useUpdateArchivalSettings();
  const triggerMutation = useTriggerArchival();

  const [archiveEnabled, setArchiveEnabled] = useState(false);
  const [archiveDays, setArchiveDays] = useState<string>('90');
  const [deleteEnabled, setDeleteEnabled] = useState(false);
  const [deleteDays, setDeleteDays] = useState<string>('365');
  const [hasInitialized, setHasInitialized] = useState(false);

  useEffect(() => {
    if (data && !hasInitialized) {
      const s = data.settings;
      setArchiveEnabled(s.archive_after_days !== null);
      setArchiveDays(s.archive_after_days?.toString() ?? '90');
      setDeleteEnabled(s.delete_after_days !== null);
      setDeleteDays(s.delete_after_days?.toString() ?? '365');
      setHasInitialized(true);
    }
  }, [data, hasInitialized]);

  const hasChanges = useMemo(() => {
    if (!data) return false;
    const s = data.settings;
    const newArchive = archiveEnabled ? parseInt(archiveDays) || null : null;
    const newDelete = deleteEnabled ? parseInt(deleteDays) || null : null;
    return (
      newArchive !== s.archive_after_days || newDelete !== s.delete_after_days
    );
  }, [data, archiveEnabled, archiveDays, deleteEnabled, deleteDays]);

  const validationError = useMemo(() => {
    if (
      archiveEnabled &&
      (isNaN(parseInt(archiveDays)) || parseInt(archiveDays) < 1)
    ) {
      return 'Archive days must be at least 1';
    }
    if (
      deleteEnabled &&
      (isNaN(parseInt(deleteDays)) || parseInt(deleteDays) < 1)
    ) {
      return 'Delete days must be at least 1';
    }
    return null;
  }, [archiveEnabled, archiveDays, deleteEnabled, deleteDays]);

  const policyWarning = useMemo(() => {
    if (archiveEnabled && deleteEnabled) {
      const a = parseInt(archiveDays);
      const d = parseInt(deleteDays);
      if (!isNaN(a) && !isNaN(d) && d <= a) {
        return `Retention (${d}d) triggers before archival (${a}d) — data will be deleted before it can be archived. Archival is effectively disabled with this configuration.`;
      }
    }
    return null;
  }, [archiveEnabled, archiveDays, deleteEnabled, deleteDays]);

  const handleSave = async () => {
    if (validationError) return;
    const newArchive = archiveEnabled ? parseInt(archiveDays) : null;
    const newDelete = deleteEnabled ? parseInt(deleteDays) : null;
    await updateMutation.mutateAsync({
      archive_after_days: newArchive,
      delete_after_days: newDelete,
    });
  };

  if (isLoading) {
    return (
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-12">
        <div className="flex items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-zinc-400" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-12 text-center">
        <p className="text-zinc-400 mb-4">Failed to load archival settings</p>
        <Button variant="outline" onClick={() => refetch()}>
          Retry
        </Button>
      </div>
    );
  }

  const storage = data?.storage;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-medium text-white">Data Lifecycle</h2>
          <p className="text-sm text-zinc-500 mt-1">
            Configure data archival and retention policies for time-series data
          </p>
        </div>
        <div className="flex gap-2">
          {hasChanges && (
            <Button
              onClick={handleSave}
              disabled={updateMutation.isPending || !!validationError}
            >
              {updateMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <CheckCircle2 className="h-4 w-4" />
                  Save Changes
                </>
              )}
            </Button>
          )}
        </div>
      </div>

      {/* Storage Overview */}
      {storage && (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
          <div className="px-6 py-4 border-b border-zinc-800 flex items-center gap-2">
            <HardDrive className="h-4 w-4 text-zinc-400" />
            <h3 className="text-sm font-medium text-white">Storage Overview</h3>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StorageStat
                label="Live Data (data_point_series)"
                value={storage.live_total_pretty}
                sub={`${storage.live_row_count.toLocaleString()} rows`}
                detail={`${storage.live_data_pretty} + ${storage.live_index_pretty} indexes`}
              />
              <StorageStat
                label="Archive Data"
                value={storage.archive_total_pretty}
                sub={`${storage.archive_row_count.toLocaleString()} rows`}
                detail={`${storage.archive_data_pretty} + ${storage.archive_index_pretty} indexes`}
              />
              <StorageStat
                label="Other Tables"
                value={storage.other_tables_pretty}
              />
              <StorageStat
                label="Total Database"
                value={storage.total_pretty}
                highlight
              />
            </div>
          </div>
        </div>
      )}

      {/* Growth Projection */}
      {storage && (
        <GrowthProjection
          storage={storage}
          archiveEnabled={archiveEnabled}
          archiveDays={parseInt(archiveDays) || 90}
          deleteEnabled={deleteEnabled}
          deleteDays={parseInt(deleteDays) || 365}
        />
      )}

      {/* Archival Settings */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-zinc-800 flex items-center gap-2">
          <Archive className="h-4 w-4 text-zinc-400" />
          <h3 className="text-sm font-medium text-white">Archival Policy</h3>
        </div>
        <div className="p-6 space-y-4">
          <p className="text-sm text-zinc-500">
            When enabled, per-sample time-series data older than the configured
            threshold is aggregated into daily summaries. This dramatically
            reduces storage while preserving aggregate accuracy.
          </p>

          <div className="flex items-center justify-between">
            <Label htmlFor="archive-toggle" className="text-white">
              Enable archival
            </Label>
            <Switch
              id="archive-toggle"
              checked={archiveEnabled}
              onCheckedChange={setArchiveEnabled}
            />
          </div>

          {archiveEnabled && (
            <div className="flex items-center gap-3">
              <Label
                htmlFor="archive-days"
                className="text-zinc-400 whitespace-nowrap"
              >
                Archive data older than
              </Label>
              <Input
                id="archive-days"
                type="number"
                min={1}
                max={3650}
                value={archiveDays}
                onChange={(e) => setArchiveDays(e.target.value)}
                className="w-24"
              />
              <span className="text-zinc-400 text-sm">days</span>
            </div>
          )}
        </div>
      </div>

      {/* Retention / Deletion Settings */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-zinc-800 flex items-center gap-2">
          <Trash2 className="h-4 w-4 text-zinc-400" />
          <h3 className="text-sm font-medium text-white">Retention Policy</h3>
        </div>
        <div className="p-6 space-y-4">
          <p className="text-sm text-zinc-500">
            When enabled, data older than the configured threshold is
            permanently deleted. Without archival, rows are deleted directly
            from the live table. With archival, only archived aggregates are
            deleted. This is irreversible.
          </p>

          <div className="flex items-center justify-between">
            <Label htmlFor="delete-toggle" className="text-white">
              Enable automatic deletion
            </Label>
            <Switch
              id="delete-toggle"
              checked={deleteEnabled}
              onCheckedChange={setDeleteEnabled}
            />
          </div>

          {deleteEnabled && (
            <div className="flex items-center gap-3">
              <Label
                htmlFor="delete-days"
                className="text-zinc-400 whitespace-nowrap"
              >
                Delete data older than
              </Label>
              <Input
                id="delete-days"
                type="number"
                min={1}
                max={7300}
                value={deleteDays}
                onChange={(e) => setDeleteDays(e.target.value)}
                className="w-24"
              />
              <span className="text-zinc-400 text-sm">days</span>
            </div>
          )}
        </div>
      </div>

      {/* Policy Warning */}
      {policyWarning && (
        <div className="flex items-center gap-2 text-amber-400 bg-amber-400/10 border border-amber-400/20 rounded-lg px-4 py-3 text-sm">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {policyWarning}
        </div>
      )}

      {/* Validation Error */}
      {validationError && (
        <div className="flex items-center gap-2 text-amber-400 bg-amber-400/10 border border-amber-400/20 rounded-lg px-4 py-3 text-sm">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {validationError}
        </div>
      )}

      {/* Manual Trigger */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-zinc-800 flex items-center gap-2">
          <Play className="h-4 w-4 text-zinc-400" />
          <h3 className="text-sm font-medium text-white">Manual Trigger</h3>
        </div>
        <div className="p-6 flex items-center justify-between">
          <p className="text-sm text-zinc-500">
            Run the archival and retention job immediately instead of waiting
            for the daily schedule.
          </p>
          <Button
            variant="outline"
            onClick={() => triggerMutation.mutate()}
            disabled={triggerMutation.isPending}
          >
            {triggerMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Running...
              </>
            ) : (
              <>
                <Play className="h-4 w-4" />
                Run Now
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}

function StorageStat({
  label,
  value,
  sub,
  detail,
  highlight,
}: {
  label: string;
  value: string;
  sub?: string;
  detail?: string;
  highlight?: boolean;
}) {
  return (
    <div className="space-y-1">
      <p className="text-xs text-zinc-500">{label}</p>
      <div className="flex items-baseline gap-1.5 flex-wrap">
        <p
          className={`text-lg font-medium ${highlight ? 'text-blue-400' : 'text-white'}`}
        >
          {value}
        </p>
        {detail && <p className="text-[10px] text-zinc-600">({detail})</p>}
      </div>
      {sub && <p className="text-xs text-zinc-600">{sub}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Growth Projection
// ---------------------------------------------------------------------------

const PROJECTION_MONTHS = 18;
const DAYS_PER_MONTH = 30;

// Volume compression: 1 day of archive ≈ 1/500 of 1 day of raw samples.
// Raw = ~1440 samples/day (1-min resolution) → archive = 1 row/day per series.
const VOLUME_COMPRESSION = 0.002;

const GROWTH_CONFIG = {
  bounded: {
    label: 'O(1) — Bounded',
    color: 'text-emerald-400',
    bg: 'bg-emerald-400/10 border-emerald-400/20',
    chartColor: '#34d399',
    description:
      'Storage is capped. Old data is deleted after the retention window and total size stabilises.',
  },
  linear_efficient: {
    label: 'O(n) — Linear (efficient)',
    color: 'text-amber-400',
    bg: 'bg-amber-400/10 border-amber-400/20',
    chartColor: '#fbbf24',
    description:
      'Live data is bounded by the archive window. Daily aggregates accumulate indefinitely at ~1/500 of the raw rate.',
  },
  linear: {
    label: 'O(n) — Linear',
    color: 'text-red-400',
    bg: 'bg-red-400/10 border-red-400/20',
    chartColor: '#f87171',
    description:
      'All raw samples are kept forever. Storage grows linearly with time and connected devices.',
  },
} as const;

type GrowthClass = keyof typeof GROWTH_CONFIG;

/**
 * Day-by-day simulation of storage growth.
 *
 * Policies are independent:
 *  - Archival only → live capped at archiveDays, excess compressed into archive.
 *  - Retention only → live capped at deleteDays (rows deleted, no archive).
 *  - Both (archive < delete) → live capped at archiveDays, archive capped
 *    at (deleteDays − archiveDays).
 *  - Both (delete ≤ archive) → archival ineffective, behaves as retention-only.
 */
function computeProjection(
  archiveEnabled: boolean,
  archiveDays: number,
  deleteEnabled: boolean,
  deleteDays: number,
  liveTotalBytes: number,
  liveRows: number,
  archiveTotalBytes: number,
  liveDataSpanDays: number
): { month: number; storage: number }[] {
  if (liveRows === 0) {
    return Array.from({ length: PROJECTION_MONTHS + 1 }, (_, m) => ({
      month: m,
      storage: liveTotalBytes + archiveTotalBytes,
    }));
  }

  const archivalEffective =
    archiveEnabled &&
    archiveDays > 0 &&
    (!deleteEnabled || deleteDays > archiveDays);

  const spanDays = Math.max(liveDataSpanDays, 1);
  const dailyRawBytes = liveTotalBytes / spanDays;
  const dailyArchiveBytes = dailyRawBytes * VOLUME_COMPRESSION;

  let liveBytes = liveTotalBytes;
  let archiveBytes = archiveTotalBytes;
  const totalDays = PROJECTION_MONTHS * DAYS_PER_MONTH;
  const points: { month: number; storage: number }[] = [];

  for (let day = 0; day <= totalDays; day++) {
    if (day % DAYS_PER_MONTH === 0) {
      points.push({
        month: day / DAYS_PER_MONTH,
        storage: Math.round(liveBytes + archiveBytes),
      });
    }

    liveBytes += dailyRawBytes;

    if (archivalEffective) {
      const liveCap = archiveDays * dailyRawBytes;
      if (liveBytes > liveCap) {
        const excess = liveBytes - liveCap;
        liveBytes = liveCap;
        archiveBytes += excess * VOLUME_COMPRESSION;
      }

      if (deleteEnabled && deleteDays > archiveDays) {
        const archiveWindowDays = deleteDays - archiveDays;
        const archiveCap = archiveWindowDays * dailyArchiveBytes;
        if (archiveBytes > archiveCap) {
          archiveBytes = archiveCap;
        }
      }
    } else if (deleteEnabled && deleteDays > 0) {
      const liveCap = deleteDays * dailyRawBytes;
      if (liveBytes > liveCap) {
        liveBytes = liveCap;
      }
    }
  }

  return points;
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(Math.abs(bytes)) / Math.log(1024));
  const idx = Math.min(i, units.length - 1);
  return `${(bytes / 1024 ** idx).toFixed(idx === 0 ? 0 : 1)} ${units[idx]}`;
}

function GrowthProjection({
  storage,
  archiveEnabled,
  archiveDays,
  deleteEnabled,
  deleteDays,
}: {
  storage: StorageEstimate;
  archiveEnabled: boolean;
  archiveDays: number;
  deleteEnabled: boolean;
  deleteDays: number;
}) {
  const archivalEffective =
    archiveEnabled &&
    archiveDays > 0 &&
    (!deleteEnabled || deleteDays > archiveDays);

  const growthClass: GrowthClass = useMemo(() => {
    if (deleteEnabled) return 'bounded';
    if (archiveEnabled) return 'linear_efficient';
    return 'linear';
  }, [archiveEnabled, deleteEnabled]);

  const cfg = GROWTH_CONFIG[growthClass];

  const liveTotalBytes = storage.live_data_bytes + storage.live_index_bytes;
  const spanDays = Math.max(storage.live_data_span_days, 1);

  const dailyRawEstimate = useMemo(() => {
    if (storage.live_row_count === 0) return 0;
    return liveTotalBytes / spanDays;
  }, [storage.live_row_count, liveTotalBytes, spanDays]);

  const chartData = useMemo(
    () =>
      computeProjection(
        archiveEnabled,
        archiveDays,
        deleteEnabled,
        deleteDays,
        liveTotalBytes,
        storage.live_row_count,
        storage.archive_data_bytes + storage.archive_index_bytes,
        storage.live_data_span_days
      ),
    [
      archiveEnabled,
      archiveDays,
      deleteEnabled,
      deleteDays,
      liveTotalBytes,
      storage.live_row_count,
      storage.archive_data_bytes,
      storage.archive_index_bytes,
      storage.live_data_span_days,
    ]
  );

  return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
      <div className="px-6 py-4 border-b border-zinc-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-zinc-400" />
          <h3 className="text-sm font-medium text-white">Growth Projection</h3>
        </div>
        <span
          className={`text-xs font-mono font-semibold px-2.5 py-1 rounded-full border ${cfg.bg} ${cfg.color}`}
        >
          {cfg.label}
        </span>
      </div>

      <div className="p-6 space-y-4">
        <p className="text-sm text-zinc-500">{cfg.description}</p>

        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart
              data={chartData}
              margin={{ top: 5, right: 10, left: 10, bottom: 0 }}
            >
              <defs>
                <linearGradient id="growthGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop
                    offset="5%"
                    stopColor={cfg.chartColor}
                    stopOpacity={0.3}
                  />
                  <stop
                    offset="95%"
                    stopColor={cfg.chartColor}
                    stopOpacity={0.02}
                  />
                </linearGradient>
              </defs>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="#27272a"
                vertical={false}
              />
              <XAxis
                dataKey="month"
                stroke="#52525b"
                tick={{ fill: '#71717a', fontSize: 11 }}
                tickFormatter={(m: number) => `${m}m`}
              />
              <YAxis
                stroke="#52525b"
                tick={{ fill: '#71717a', fontSize: 11 }}
                tickFormatter={(v: number) => formatBytes(v)}
                width={60}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#18181b',
                  border: '1px solid #3f3f46',
                  borderRadius: '8px',
                  fontSize: 12,
                }}
                labelFormatter={(m: number) => `Month ${m} (day ${m * 30})`}
                formatter={(v: number) => [formatBytes(v), 'Estimated size']}
              />
              <Area
                type="monotone"
                dataKey="storage"
                stroke={cfg.chartColor}
                strokeWidth={2}
                fill="url(#growthGradient)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="space-y-1 text-xs text-zinc-600">
          {storage.live_row_count > 0 ? (
            <p>
              Daily ingest estimate:{' '}
              <strong className="text-zinc-500">
                ~{formatBytes(dailyRawEstimate)}/day
              </strong>{' '}
              = live table ({formatBytes(liveTotalBytes)}) ÷ {spanDays} days of
              data.
              {archivalEffective &&
                ' Archive compression ≈ 1/500 of raw volume.'}
            </p>
          ) : (
            <p>
              No live data yet — projection shows a flat line at the current
              database size.
            </p>
          )}
          <p>
            Estimates are approximate and depend on connected devices, data
            frequency, and schema changes.
          </p>
        </div>
      </div>
    </div>
  );
}

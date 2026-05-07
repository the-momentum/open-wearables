/**
 * Shared formatting helpers and label maps for sync status display.
 * Used by connection-card.tsx and the Syncs admin page.
 */

export const STAGE_LABELS: Record<string, string> = {
  queued: 'Queued',
  started: 'Starting',
  fetching: 'Fetching',
  processing: 'Processing',
  saving: 'Saving',
  completed: 'Completed',
  failed: 'Failed',
  cancelled: 'Cancelled',
};

export const SOURCE_LABELS: Record<string, string> = {
  pull: 'Live Sync',
  webhook: 'Webhook',
  sdk: 'SDK Upload',
  backfill: 'Historical Sync',
  xml_import: 'XML Import',
};

export const RUN_STATUS_CLASSES: Record<string, string> = {
  success:
    'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300',
  partial:
    'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
  failed: 'bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300',
  cancelled: 'bg-zinc-200 text-zinc-700 dark:bg-zinc-800/60 dark:text-zinc-300',
  in_progress:
    'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
};

export function formatRunDuration(
  start: string | null,
  end: string | null
): string {
  if (!start || !end) return '—';
  const ms = new Date(end).getTime() - new Date(start).getTime();
  if (ms < 0 || !Number.isFinite(ms)) return '—';
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${m}m ${rem}s`;
}

export function formatRelative(iso: string | null): string {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  const diff = Date.now() - date.getTime();
  if (diff < 0) return date.toLocaleString();
  const s = Math.floor(diff / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return date.toLocaleString();
}

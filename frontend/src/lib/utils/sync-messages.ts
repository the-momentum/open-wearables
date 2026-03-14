import type { SyncEvent } from '@/lib/api/types';

/**
 * Convert a raw SSE sync event into a human-readable status message.
 */
export function buildSyncMessage(event: SyncEvent): string {
  const provider = event.provider || 'Provider';
  const data = event.data || {};

  switch (event.type) {
    case 'sync:started': {
      const count = (data.total_providers as number) ?? 0;
      return `Starting sync for ${count} provider${count !== 1 ? 's' : ''}…`;
    }
    case 'sync:provider:started':
      return `Connecting to ${provider}…`;
    case 'sync:provider:workouts:started':
      return `Fetching workouts from ${provider}…`;
    case 'sync:provider:workouts:completed':
      return `Workouts from ${provider} downloaded`;
    case 'sync:provider:workouts:error':
      return `Failed to fetch workouts from ${provider}`;
    case 'sync:provider:247:started':
      return `Fetching health data (sleep, activity) from ${provider}…`;
    case 'sync:provider:247:completed':
      return `Health data from ${provider} downloaded`;
    case 'sync:provider:247:error':
      return `Failed to fetch health data from ${provider}`;
    case 'sync:provider:completed':
      return `${provider} sync complete`;
    case 'sync:provider:error':
      return `${provider} sync failed`;
    case 'sync:completed':
      return 'Sync completed successfully';
    case 'sync:error':
      return `Sync error: ${(data.error as string) ?? 'Unknown error'}`;
    default:
      return '';
  }
}

/**
 * Determine the current high-level step from the event type.
 */
export function getStepFromEvent(eventType: string): 'workouts' | '247' | null {
  if (eventType.includes('workouts')) return 'workouts';
  if (eventType.includes('247')) return '247';
  return null;
}

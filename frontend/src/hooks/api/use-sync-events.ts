import { useCallback, useEffect, useRef, useState } from 'react';
import { API_CONFIG, API_ENDPOINTS } from '@/lib/api/config';
import { getToken } from '@/lib/auth/session';
import type { SyncEvent, SyncProgress } from '@/lib/api/types';
import { queryClient } from '@/lib/query/client';
import { queryKeys } from '@/lib/query/keys';
import { buildSyncMessage, getStepFromEvent } from '@/lib/utils/sync-messages';

const INITIAL_PROGRESS: SyncProgress = {
  active: false,
  taskId: null,
  providers: [],
  currentProvider: null,
  message: '',
  currentStep: null,
  currentIndex: 0,
  totalProviders: 0,
  events: [],
  completedProviders: [],
  errorProviders: [],
};

/**
 * Hook that manages an SSE connection for real-time sync progress.
 *
 * Returns:
 * - `progress`: current SyncProgress state
 * - `startListening(userId)`: opens an EventSource for the given user
 * - `stopListening()`: manually close the connection
 */
export function useSyncEvents(userId: string) {
  const [progress, setProgress] = useState<SyncProgress>(INITIAL_PROGRESS);
  const eventSourceRef = useRef<EventSource | null>(null);

  const stopListening = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  // Clean up on unmount
  useEffect(() => {
    return () => stopListening();
  }, [stopListening]);

  const startListening = useCallback(() => {
    // Close any existing connection
    stopListening();

    const token = getToken();
    if (!token) return;

    const url = `${API_CONFIG.baseUrl}${API_ENDPOINTS.syncEvents(userId)}?token=${encodeURIComponent(token)}`;
    const es = new EventSource(url);
    eventSourceRef.current = es;

    // Reset progress
    setProgress({ ...INITIAL_PROGRESS, active: true });

    const handleMessage = (e: MessageEvent) => {
      try {
        const event: SyncEvent = JSON.parse(e.data);

        setProgress((prev) => {
          const events = [...prev.events, event];
          const next: SyncProgress = { ...prev, events };

          switch (event.type) {
            case 'sync:started':
              next.providers = (event.data?.providers as string[]) ?? [];
              next.totalProviders =
                (event.data?.total_providers as number) ?? 0;
              next.taskId = event.task_id ?? null;
              break;

            case 'sync:provider:started':
              next.currentProvider = event.provider ?? null;
              next.currentIndex =
                (event.data?.index as number) ?? prev.currentIndex;
              next.currentStep = null;
              break;

            case 'sync:provider:workouts:started':
            case 'sync:provider:workouts:completed':
            case 'sync:provider:workouts:error':
            case 'sync:provider:247:started':
            case 'sync:provider:247:completed':
            case 'sync:provider:247:error':
              next.currentStep = getStepFromEvent(event.type);
              break;

            case 'sync:provider:completed':
              if (event.provider) {
                next.completedProviders = [
                  ...prev.completedProviders,
                  event.provider,
                ];
              }
              next.currentStep = null;
              break;

            case 'sync:provider:error':
              if (event.provider) {
                next.errorProviders = [...prev.errorProviders, event.provider];
              }
              next.currentStep = null;
              break;

            case 'sync:completed':
              next.active = false;
              next.currentProvider = null;
              next.currentStep = null;
              break;

            case 'sync:error':
              next.active = false;
              next.currentProvider = null;
              next.currentStep = null;
              break;
          }

          next.message = buildSyncMessage(event);
          return next;
        });

        // Handle side effects outside setProgress
        if (event.type === 'sync:completed') {
          queryClient.invalidateQueries({
            queryKey: queryKeys.connections.all(userId),
          });
          queryClient.invalidateQueries({
            queryKey: queryKeys.health.workouts(userId),
          });
          queryClient.invalidateQueries({
            queryKey: queryKeys.health.activitySummaries(userId),
          });
          queryClient.invalidateQueries({
            queryKey: queryKeys.health.sleepSessions(userId),
          });
          queryClient.invalidateQueries({
            queryKey: queryKeys.health.bodySummary(userId),
          });
        }

        // Close EventSource on terminal events
        if (event.type === 'sync:completed' || event.type === 'sync:error') {
          es.close();
          eventSourceRef.current = null;
        }
      } catch {
        // Ignore malformed messages
      }
    };

    const ALL_EVENTS = [
      'sync:started',
      'sync:provider:started',
      'sync:provider:workouts:started',
      'sync:provider:workouts:completed',
      'sync:provider:workouts:error',
      'sync:provider:247:started',
      'sync:provider:247:completed',
      'sync:provider:247:error',
      'sync:provider:completed',
      'sync:provider:error',
      'sync:completed',
      'sync:error',
    ];

    for (const eventName of ALL_EVENTS) {
      es.addEventListener(eventName, handleMessage);
    }

    es.onerror = () => {
      // EventSource auto-reconnects on most errors.
      // Reset progress to inactive in non-open states
      if (es.readyState !== EventSource.OPEN) {
        setProgress({ ...INITIAL_PROGRESS, active: false });
      }

      // If the connection is closed by server, readyState becomes CLOSED.
      if (es.readyState === EventSource.CLOSED) {
        eventSourceRef.current = null;
      }
    };
  }, [userId, stopListening]);

  const reset = useCallback(() => {
    stopListening();
    setProgress(INITIAL_PROGRESS);
  }, [stopListening]);

  return { progress, startListening, stopListening, reset };
}

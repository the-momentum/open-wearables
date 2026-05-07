import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState, useCallback } from 'react';
import { syncStatusService } from '../../lib/api';
import type { SyncStatusEvent } from '../../lib/api';
import { queryKeys } from '../../lib/query/keys';

export function useRecentSyncs(userId: string, limit = 50, enabled = true) {
  return useQuery({
    queryKey: queryKeys.syncStatus.recent(userId, limit),
    queryFn: () => syncStatusService.getRecent(userId, limit),
    enabled: !!userId && enabled,
    refetchOnWindowFocus: false,
  });
}

export function useSyncRuns(userId: string, limit = 20, enabled = true) {
  return useQuery({
    queryKey: queryKeys.syncStatus.runs(userId, limit),
    queryFn: () => syncStatusService.getRuns(userId, limit),
    enabled: !!userId && enabled,
    refetchOnWindowFocus: false,
  });
}

export interface AllSyncRunsFilters {
  user_id?: string;
  provider?: string;
  status?: string;
  source?: string;
}

export function useAllSyncRuns(
  filters: AllSyncRunsFilters = {},
  limit = 50,
  enabled = true
) {
  return useQuery({
    queryKey: queryKeys.syncStatus.allRuns(
      filters as Record<string, string | undefined>,
      limit
    ),
    queryFn: () => syncStatusService.getAllRuns({ ...filters, limit }),
    enabled,
    refetchOnWindowFocus: false,
  });
}

export interface UseSyncStatusStreamResult {
  events: SyncStatusEvent[];
  activeRuns: Map<string, SyncStatusEvent>;
  connected: boolean;
  error: string | null;
  reconnect: () => void;
}

interface SSEMessage {
  event?: string;
  data?: string;
}

function parseEvent(block: string): SSEMessage | null {
  const lines = block.split('\n');
  const msg: SSEMessage = {};
  for (const line of lines) {
    if (!line || line.startsWith(':')) continue;
    const idx = line.indexOf(':');
    if (idx === -1) continue;
    const field = line.slice(0, idx).trim();
    const value = line.slice(idx + 1).replace(/^\s/, '');
    if (field === 'event') msg.event = value;
    else if (field === 'data')
      msg.data = msg.data === undefined ? value : `${msg.data}\n${value}`;
  }
  return msg.data !== undefined ? msg : null;
}

/**
 * Subscribe to live sync-status SSE for a user. Streams events into local
 * state and tracks the latest event per run_id so the UI can render banners.
 */
export function useSyncStatusStream(
  userId: string | undefined,
  enabled = true,
  replay = 20
): UseSyncStatusStreamResult {
  const [events, setEvents] = useState<SyncStatusEvent[]>([]);
  const [activeRuns, setActiveRuns] = useState<Map<string, SyncStatusEvent>>(
    () => new Map()
  );
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const [reconnectKey, setReconnectKey] = useState(0);
  const queryClient = useQueryClient();

  const reconnect = useCallback(() => {
    setReconnectKey((k) => k + 1);
  }, []);

  useEffect(() => {
    if (!userId || !enabled) return;

    // Clear any events/runs from a previous user before opening a new stream.
    setEvents([]);
    setActiveRuns(new Map());

    let cancelled = false;
    const controller = new AbortController();
    abortRef.current = controller;

    const TERMINAL_STATUSES = new Set([
      'success',
      'failed',
      'partial',
      'cancelled',
    ]);

    const handleEvent = (evt: SyncStatusEvent) => {
      setEvents((prev) => {
        const next = [evt, ...prev];
        return next.slice(0, 200);
      });
      const isTerminal = TERMINAL_STATUSES.has(evt.status);
      setActiveRuns((prev) => {
        const next = new Map(prev);
        if (isTerminal) {
          next.delete(evt.run_id);
        } else {
          next.set(evt.run_id, evt);
        }
        return next;
      });
      // Invalidate sync data queries so UI refreshes after sync completes
      if (isTerminal) {
        queryClient.invalidateQueries({ queryKey: queryKeys.syncStatus.all });
      }
      // Invalidate connections whenever a sync starts — a new provider may
      // have just been paired, so the connections list should refresh.
      if (evt.stage === 'started' && userId) {
        queryClient.invalidateQueries({
          queryKey: queryKeys.connections.all(userId),
        });
      }
    };

    const run = async () => {
      try {
        const response = await syncStatusService.openStream(
          userId,
          replay,
          controller.signal
        );
        if (!response.ok || !response.body) {
          setError(`Stream error: ${response.status}`);
          setConnected(false);
          return;
        }
        setConnected(true);
        setError(null);

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (!cancelled) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          let sepIdx: number;
          while ((sepIdx = buffer.indexOf('\n\n')) !== -1) {
            const block = buffer.slice(0, sepIdx);
            buffer = buffer.slice(sepIdx + 2);
            const msg = parseEvent(block);
            if (!msg || !msg.data) continue;
            if (msg.event && msg.event !== 'sync.status') continue;
            try {
              const parsed = JSON.parse(msg.data) as SyncStatusEvent;
              handleEvent(parsed);
            } catch {
              // ignore malformed
            }
          }
        }
        setConnected(false);
      } catch (err) {
        if (cancelled || (err as Error).name === 'AbortError') return;
        setConnected(false);
        setError((err as Error).message ?? 'Stream error');
      }
    };

    run();

    return () => {
      cancelled = true;
      controller.abort();
      setConnected(false);
    };
  }, [userId, enabled, replay, reconnectKey, queryClient]);

  return { events, activeRuns, connected, error, reconnect };
}

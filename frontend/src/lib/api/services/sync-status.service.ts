import { apiClient } from '../client';
import { API_ENDPOINTS } from '../config';

export type SyncSource = 'pull' | 'webhook' | 'sdk' | 'backfill' | 'xml_import';
export type SyncStage =
  | 'queued'
  | 'started'
  | 'fetching'
  | 'processing'
  | 'saving'
  | 'completed'
  | 'failed'
  | 'cancelled';
export type SyncStatus =
  | 'in_progress'
  | 'success'
  | 'partial'
  | 'failed'
  | 'cancelled';

export interface SyncStatusEvent {
  event_id: string;
  run_id: string;
  user_id: string;
  provider: string;
  source: SyncSource;
  stage: SyncStage;
  status: SyncStatus;
  message: string | null;
  progress: number | null;
  items_processed: number | null;
  items_total: number | null;
  error: string | null;
  metadata: Record<string, unknown>;
  started_at: string | null;
  ended_at: string | null;
  timestamp: string;
}

export interface SyncRunSummary {
  run_id: string;
  user_id: string;
  provider: string;
  source: string;
  stage: string;
  status: string;
  message: string | null;
  progress: number | null;
  items_processed: number | null;
  items_total: number | null;
  error: string | null;
  started_at: string | null;
  ended_at: string | null;
  last_update: string;
}

export const syncStatusService = {
  getRecent(userId: string, limit = 50): Promise<SyncStatusEvent[]> {
    return apiClient.get<SyncStatusEvent[]>(
      API_ENDPOINTS.syncStatusRecent(userId),
      { params: { limit } }
    );
  },

  getRuns(userId: string, limit = 20): Promise<SyncRunSummary[]> {
    return apiClient.get<SyncRunSummary[]>(
      API_ENDPOINTS.syncStatusRuns(userId),
      {
        params: { limit },
      }
    );
  },

  getAllRuns(
    params: {
      limit?: number;
      user_id?: string;
      provider?: string;
      status?: string;
      source?: string;
    } = {}
  ): Promise<SyncRunSummary[]> {
    return apiClient.get<SyncRunSummary[]>(API_ENDPOINTS.syncStatusAllRuns, {
      params,
    });
  },

  /**
   * Open the SSE stream via the shared apiClient so 401 responses trigger
   * the centralized session-clear / redirect logic.
   *
   * Returns the raw Response; consumers iterate the body via a TextDecoder.
   */
  openStream(
    userId: string,
    replay = 20,
    signal?: AbortSignal
  ): Promise<Response> {
    return apiClient.fetchRaw(API_ENDPOINTS.syncStatusStream(userId), {
      params: { replay: String(replay) },
      headers: {
        Accept: 'text/event-stream',
        'Cache-Control': 'no-cache',
      },
      credentials: 'include',
      signal,
    });
  },
};

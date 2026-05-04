import { apiClient } from '../client';
import { API_CONFIG, API_ENDPOINTS } from '../config';
import { getToken } from '../../auth/session';

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
   * Open the SSE stream using fetch + ReadableStream so we can send the
   * developer JWT via Authorization header (EventSource cannot).
   *
   * Returns the raw Response; consumers iterate the body via a TextDecoder.
   */
  async openStream(
    userId: string,
    replay = 20,
    signal?: AbortSignal
  ): Promise<Response> {
    const token = getToken();
    const params = new URLSearchParams();
    params.set('replay', String(replay));
    const url = `${API_CONFIG.baseUrl}${API_ENDPOINTS.syncStatusStream(userId)}?${params.toString()}`;
    const headers: Record<string, string> = {
      Accept: 'text/event-stream',
      'Cache-Control': 'no-cache',
    };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    return fetch(url, { headers, signal, credentials: 'include' });
  },
};

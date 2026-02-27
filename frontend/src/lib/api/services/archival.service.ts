import { apiClient } from '../client';
import { ApiError } from '../../errors/api-error';

// Types
export interface ArchivalSettings {
  archive_after_days: number | null;
  delete_after_days: number | null;
}

export interface StorageEstimate {
  live_data_bytes: number;
  live_index_bytes: number;
  archive_data_bytes: number;
  archive_index_bytes: number;
  other_tables_bytes: number;
  total_bytes: number;
  live_row_count: number;
  archive_row_count: number;
  avg_bytes_per_live_row: number;
  avg_bytes_per_archive_row: number;
  live_total_pretty: string;
  live_data_pretty: string;
  live_index_pretty: string;
  archive_total_pretty: string;
  archive_data_pretty: string;
  archive_index_pretty: string;
  other_tables_pretty: string;
  total_pretty: string;
  growth_class: 'bounded' | 'linear_efficient' | 'linear';
}

export interface ArchivalSettingsWithEstimate {
  settings: ArchivalSettings;
  storage: StorageEstimate;
}

export interface ArchivalSettingsUpdate {
  archive_after_days: number | null;
  delete_after_days: number | null;
}

export interface ArchivalRunResult {
  task_id: string;
  status: string;
}

// Service
export const archivalService = {
  async getSettings(): Promise<ArchivalSettingsWithEstimate> {
    try {
      return await apiClient.get<ArchivalSettingsWithEstimate>(
        '/api/v1/settings/archival'
      );
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw ApiError.networkError((error as Error).message);
    }
  },

  async updateSettings(
    data: ArchivalSettingsUpdate
  ): Promise<ArchivalSettingsWithEstimate> {
    try {
      return await apiClient.put<ArchivalSettingsWithEstimate>(
        '/api/v1/settings/archival',
        data
      );
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw ApiError.networkError((error as Error).message);
    }
  },

  async triggerArchival(): Promise<ArchivalRunResult> {
    try {
      return await apiClient.post<ArchivalRunResult>(
        '/api/v1/settings/archival/run',
        {}
      );
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw ApiError.networkError((error as Error).message);
    }
  },
};

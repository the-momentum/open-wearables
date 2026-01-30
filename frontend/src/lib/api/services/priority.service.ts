import { apiClient } from '../client';
import { ApiError } from '../../errors/api-error';

// Provider enum matching backend ProviderName
export type ProviderName = 'apple' | 'garmin' | 'polar' | 'suunto' | 'whoop' | 'unknown';

// Device type enum matching backend DeviceType
export type DeviceType = 'watch' | 'band' | 'ring' | 'phone' | 'scale' | 'other' | 'unknown';

// Types
export interface ProviderPriority {
  id: string;
  provider: ProviderName;
  priority: number;
  created_at: string;
  updated_at: string;
}

export interface ProviderPriorityListResponse {
  items: ProviderPriority[];
}

export interface ProviderPriorityUpdate {
  priority: number;
}

export interface ProviderPriorityBulkUpdate {
  priorities: { provider: ProviderName; priority: number }[];
}

export interface DataSource {
  id: string;
  user_id: string;
  provider: ProviderName;
  user_connection_id: string | null;
  device_model: string | null;
  software_version: string | null;
  source: string | null;
  device_type: DeviceType | null;
  is_enabled: boolean;
  original_source_name: string | null;
  display_name: string | null;
}

export interface DataSourceListResponse {
  items: DataSource[];
  total: number;
}

export interface DataSourceEnableUpdate {
  is_enabled: boolean;
}

// Service
export const priorityService = {
  // Provider Priorities (global)
  async getProviderPriorities(): Promise<ProviderPriority[]> {
    try {
      const response =
        await apiClient.get<ProviderPriorityListResponse>(
          '/priorities/providers'
        );
      return response.items;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw ApiError.networkError((error as Error).message);
    }
  },

  async updateProviderPriority(
    provider: string,
    data: ProviderPriorityUpdate
  ): Promise<ProviderPriority> {
    try {
      const response = await apiClient.put<ProviderPriority>(
        `/priorities/providers/${provider}`,
        data
      );
      return response;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw ApiError.networkError((error as Error).message);
    }
  },

  async bulkUpdateProviderPriorities(
    data: ProviderPriorityBulkUpdate
  ): Promise<ProviderPriority[]> {
    try {
      const response = await apiClient.put<ProviderPriorityListResponse>(
        '/priorities/providers',
        data
      );
      return response.items;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw ApiError.networkError((error as Error).message);
    }
  },

  // User Data Sources
  async getUserDataSources(userId: string): Promise<DataSource[]> {
    try {
      const response = await apiClient.get<DataSourceListResponse>(
        `/users/${userId}/data-sources`
      );
      return response.items;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw ApiError.networkError((error as Error).message);
    }
  },

  async updateDataSourceEnabled(
    userId: string,
    dataSourceId: string,
    data: DataSourceEnableUpdate
  ): Promise<DataSource> {
    try {
      const response = await apiClient.patch<DataSource>(
        `/users/${userId}/data-sources/${dataSourceId}`,
        data
      );
      return response;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw ApiError.networkError((error as Error).message);
    }
  },
};

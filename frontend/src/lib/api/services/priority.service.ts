import { apiClient } from '../client';
import { ApiError } from '../../errors/api-error';

// Provider enum matching backend ProviderName
export type ProviderName =
  | 'apple'
  | 'garmin'
  | 'polar'
  | 'suunto'
  | 'whoop'
  | 'oura'
  | 'unknown';

// Device type enum matching backend DeviceType
export type DeviceType =
  | 'watch'
  | 'band'
  | 'ring'
  | 'phone'
  | 'scale'
  | 'other'
  | 'unknown';

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
  original_source_name: string | null;
  display_name: string | null;
  is_enabled: boolean;
}

export interface DataSourceEnabledUpdate {
  is_enabled: boolean;
}

export interface DataSourceListResponse {
  items: DataSource[];
  total: number;
}

export interface DeviceTypePriority {
  id: string;
  device_type: DeviceType;
  priority: number;
  created_at: string;
  updated_at: string;
}

export interface DeviceTypePriorityListResponse {
  items: DeviceTypePriority[];
}

export interface DeviceTypePriorityUpdate {
  priority: number;
}

export interface DeviceTypePriorityBulkUpdate {
  priorities: { device_type: DeviceType; priority: number }[];
}

// Service
export const priorityService = {
  // Provider Priorities (global)
  async getProviderPriorities(): Promise<ProviderPriority[]> {
    try {
      const response = await apiClient.get<ProviderPriorityListResponse>(
        '/api/v1/priorities/providers'
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
        `/api/v1/priorities/providers/${provider}`,
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
        '/api/v1/priorities/providers',
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
        `/api/v1/users/${userId}/data-sources`
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
    data: DataSourceEnabledUpdate
  ): Promise<DataSource> {
    try {
      const response = await apiClient.patch<DataSource>(
        `/api/v1/users/${userId}/data-sources/${dataSourceId}`,
        data
      );
      return response;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw ApiError.networkError((error as Error).message);
    }
  },

  // Device Type Priorities (global)
  async getDeviceTypePriorities(): Promise<DeviceTypePriority[]> {
    try {
      const response = await apiClient.get<DeviceTypePriorityListResponse>(
        '/api/v1/priorities/device-types'
      );
      return response.items;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw ApiError.networkError((error as Error).message);
    }
  },

  async updateDeviceTypePriority(
    deviceType: DeviceType,
    data: DeviceTypePriorityUpdate
  ): Promise<DeviceTypePriority> {
    try {
      const response = await apiClient.put<DeviceTypePriority>(
        `/api/v1/priorities/device-types/${deviceType}`,
        data
      );
      return response;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw ApiError.networkError((error as Error).message);
    }
  },

  async bulkUpdateDeviceTypePriorities(
    data: DeviceTypePriorityBulkUpdate
  ): Promise<DeviceTypePriority[]> {
    try {
      const response = await apiClient.put<DeviceTypePriorityListResponse>(
        '/api/v1/priorities/device-types',
        data
      );
      return response.items;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw ApiError.networkError((error as Error).message);
    }
  },
};

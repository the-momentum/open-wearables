import { apiClient } from '../client';
import { API_ENDPOINTS } from '../config';
import type { ApiKey, ApiKeyCreate, ApiKeyUpdate } from '../types';

export const credentialsService = {
  async getApiKeys(): Promise<ApiKey[]> {
    return apiClient.get<ApiKey[]>(API_ENDPOINTS.apiKeys);
  },

  async getApiKey(id: string): Promise<ApiKey> {
    return apiClient.get<ApiKey>(API_ENDPOINTS.apiKeyDetail(id));
  },

  async createApiKey(data: ApiKeyCreate): Promise<ApiKey> {
    return apiClient.post<ApiKey>(API_ENDPOINTS.apiKeys, data);
  },

  async updateApiKey(id: string, data: ApiKeyUpdate): Promise<ApiKey> {
    return apiClient.patch<ApiKey>(API_ENDPOINTS.apiKeyDetail(id), data);
  },

  async deleteApiKey(id: string): Promise<ApiKey> {
    return apiClient.delete<ApiKey>(API_ENDPOINTS.apiKeyDetail(id));
  },

  async rotateApiKey(id: string): Promise<ApiKey> {
    return apiClient.post<ApiKey>(API_ENDPOINTS.apiKeyRotate(id));
  },
};

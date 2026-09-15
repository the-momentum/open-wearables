import { apiClient } from '../client';
import { API_ENDPOINTS } from '../config';
import type {
  ApiKey,
  ApiKeyCreate,
  ApiKeyUpdate,
  ApiKeyWithSecret,
} from '../types';

export const apiKeysService = {
  async getApiKeys(): Promise<ApiKey[]> {
    return apiClient.get<ApiKey[]>(API_ENDPOINTS.apiKeys);
  },

  async getApiKey(id: string): Promise<ApiKey> {
    return apiClient.get<ApiKey>(API_ENDPOINTS.apiKeyDetail(id));
  },

  /** The returned `key` is shown only once - it cannot be fetched again. */
  async createApiKey(data: ApiKeyCreate): Promise<ApiKeyWithSecret> {
    return apiClient.post<ApiKeyWithSecret>(API_ENDPOINTS.apiKeys, data);
  },

  async updateApiKey(id: string, data: ApiKeyUpdate): Promise<ApiKey> {
    return apiClient.patch<ApiKey>(API_ENDPOINTS.apiKeyDetail(id), data);
  },

  /** Revokes the old key and returns a new one; `key` is shown only once. */
  async rotateApiKey(id: string): Promise<ApiKeyWithSecret> {
    return apiClient.post<ApiKeyWithSecret>(API_ENDPOINTS.apiKeyRotate(id));
  },

  async revokeApiKey(id: string): Promise<void> {
    return apiClient.delete<void>(API_ENDPOINTS.apiKeyDetail(id));
  },

  async deleteApiKey(id: string): Promise<void> {
    return apiClient.delete<void>(API_ENDPOINTS.apiKeyDetail(id));
  },
};

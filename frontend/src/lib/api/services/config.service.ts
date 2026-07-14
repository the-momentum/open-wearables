import { apiClient } from '../client';
import { API_ENDPOINTS } from '../config';

export interface AppConfig {
  outgoing_webhooks_enabled: boolean;
}

export const configService = {
  async get(): Promise<AppConfig> {
    return apiClient.get<AppConfig>(API_ENDPOINTS.config);
  },
};

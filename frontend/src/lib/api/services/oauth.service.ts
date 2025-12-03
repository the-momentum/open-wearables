import { apiClient } from '../client';
import { API_ENDPOINTS } from '../config';
import type { Provider } from '../types';

export interface OAuthProvidersUpdate {
  providers: Record<string, boolean>;
}

export const oauthService = {
  async getProviders(cloudOnly: boolean = false, enabledOnly: boolean = false): Promise<Provider[]> {
    const params = new URLSearchParams();
    if (cloudOnly) params.append('cloud_only', 'true');
    if (enabledOnly) params.append('enabled_only', 'true');
    
    const endpoint = params.toString()
      ? `${API_ENDPOINTS.oauthProviders}?${params}`
      : API_ENDPOINTS.oauthProviders;
    
    return apiClient.get<Provider[]>(endpoint);
  },

  async updateProviders(
    data: OAuthProvidersUpdate
  ): Promise<{ providers: Provider[] }> {
    return apiClient.put<{ providers: Provider[] }>(
      API_ENDPOINTS.oauthProviders,
      data
    );
  },
};


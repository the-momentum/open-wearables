import { apiClient } from '../client';
import { API_ENDPOINTS } from '../config';
import type { Provider } from '../types';

/**
 * Update payload for OAuth provider settings.
 * Maps provider identifiers to their enabled/disabled state.
 */
export interface OAuthProvidersUpdate {
  /** Record of provider identifiers to their enabled status (true = enabled, false = disabled) */
  providers: Record<string, boolean>;
}

/**
 * Service for managing OAuth provider configurations.
 */
export const oauthService = {
  /**
   * Retrieves a list of OAuth providers.
   *
   * @param cloudOnly - If true, only returns cloud-based providers. Defaults to false.
   * @param enabledOnly - If true, only returns enabled providers. Defaults to false.
   * @returns Promise resolving to an array of Provider objects.
   */
  async getProviders(
    cloudOnly: boolean = false,
    enabledOnly: boolean = false
  ): Promise<Provider[]> {
    const params = new URLSearchParams();
    if (cloudOnly) params.append('cloud_only', 'true');
    if (enabledOnly) params.append('enabled_only', 'true');

    const endpoint = params.toString()
      ? `${API_ENDPOINTS.oauthProviders}?${params}`
      : API_ENDPOINTS.oauthProviders;

    return apiClient.get<Provider[]>(endpoint);
  },

  /**
   * Updates the enabled/disabled state of OAuth providers.
   *
   * @param data - Update payload containing provider states.
   * @returns Promise resolving to an object containing the updated list of providers.
   */
  async updateProviders(
    data: OAuthProvidersUpdate
  ): Promise<{ providers: Provider[] }> {
    return apiClient.put<{ providers: Provider[] }>(
      API_ENDPOINTS.oauthProviders,
      data
    );
  },
};

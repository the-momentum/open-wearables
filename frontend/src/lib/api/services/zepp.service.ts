import { apiClient } from '../client';
import { API_ENDPOINTS } from '../config';
import type { UserConnection } from '../types';

export interface ZeppVerifyRequest {
  app_token: string;
  user_id: string;
  host?: string;
}

export interface ZeppVerifyResponse {
  valid: boolean;
  user_id: string;
  message?: string | null;
}

export interface ZeppConnectRequest {
  app_token: string;
  provider_user_id: string;
  host?: string;
}

export const zeppService = {
  async verify(data: ZeppVerifyRequest): Promise<ZeppVerifyResponse> {
    return apiClient.post<ZeppVerifyResponse>(API_ENDPOINTS.zeppVerify, data);
  },

  async connect(
    userId: string,
    data: ZeppConnectRequest
  ): Promise<UserConnection> {
    return apiClient.post<UserConnection>(
      API_ENDPOINTS.zeppConnect(userId),
      data
    );
  },
};

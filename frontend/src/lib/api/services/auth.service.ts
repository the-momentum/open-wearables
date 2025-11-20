// Auth API service

import { apiClient } from '../client';
import { API_ENDPOINTS } from '../config';
import type { LoginRequest, AuthResponse, RegisterRequest } from '../types';

const USE_MOCK = import.meta.env.VITE_USE_MOCK_API === 'true';

// Mock auth service
const mockAuthService = {
  async login(): Promise<AuthResponse> {
    await delay(800);

    // Accept any credentials - no validation
    // Mock success response
    return {
      access_token: 'mock_token_' + Math.random().toString(36).substring(7),
      token_type: 'bearer',
      developer_id: 'dev_' + Math.random().toString(36).substring(7),
    };
  },

  async register(): Promise<AuthResponse> {
    await delay(1000);

    return {
      access_token: 'mock_token_' + Math.random().toString(36).substring(7),
      token_type: 'bearer',
      developer_id: 'dev_' + Math.random().toString(36).substring(7),
    };
  },

  async logout(): Promise<void> {
    await delay(300);
  },
};

// Real auth service
const realAuthService = {
  async login(credentials: LoginRequest): Promise<AuthResponse> {
    return apiClient.post<AuthResponse>(API_ENDPOINTS.login, credentials);
  },

  async register(data: RegisterRequest): Promise<AuthResponse> {
    return apiClient.post<AuthResponse>(API_ENDPOINTS.register, data);
  },

  async logout(): Promise<void> {
    return apiClient.post<void>(API_ENDPOINTS.logout);
  },
};

export const authService = USE_MOCK ? mockAuthService : realAuthService;

// Utility function
function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

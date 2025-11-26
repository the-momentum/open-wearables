import { apiClient } from '../client';
import { API_ENDPOINTS } from '../config';
import type {
  LoginRequest,
  AuthResponse,
  RegisterRequest,
  RegisterResponse,
  ForgotPasswordRequest,
  ResetPasswordRequest,
} from '../types';

export const authService = {
  async login(credentials: LoginRequest): Promise<AuthResponse> {
    // fastapi-users expects OAuth2 form data with username/password
    return apiClient.postForm<AuthResponse>(API_ENDPOINTS.login, {
      username: credentials.email,
      password: credentials.password,
    });
  },

  async register(data: RegisterRequest): Promise<RegisterResponse> {
    return apiClient.post<RegisterResponse>(API_ENDPOINTS.register, data);
  },

  async logout(): Promise<void> {
    return apiClient.post<void>(API_ENDPOINTS.logout);
  },

  async forgotPassword(data: ForgotPasswordRequest): Promise<void> {
    return apiClient.post<void>(API_ENDPOINTS.forgotPassword, data);
  },

  async resetPassword(data: ResetPasswordRequest): Promise<void> {
    return apiClient.post<void>(API_ENDPOINTS.resetPassword, data);
  },
};

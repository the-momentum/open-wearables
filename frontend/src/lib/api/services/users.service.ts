import { apiClient } from '../client';
import { API_ENDPOINTS } from '../config';
import type { UserRead, UserCreate, UserUpdate } from '../types';

export const usersService = {
  async getAll(filters?: { search?: string }): Promise<UserRead[]> {
    const params = new URLSearchParams();
    if (filters?.search) params.append('search', filters.search);

    const endpoint = params.toString()
      ? `${API_ENDPOINTS.users}?${params}`
      : API_ENDPOINTS.users;

    return apiClient.get<UserRead[]>(endpoint);
  },

  async getById(id: string): Promise<UserRead> {
    return apiClient.get<UserRead>(API_ENDPOINTS.userDetail(id));
  },

  async create(data: UserCreate): Promise<UserRead> {
    return apiClient.post<UserRead>(API_ENDPOINTS.users, data);
  },

  async update(id: string, data: UserUpdate): Promise<UserRead> {
    return apiClient.patch<UserRead>(API_ENDPOINTS.userDetail(id), data);
  },

  async delete(id: string): Promise<void> {
    return apiClient.delete<void>(API_ENDPOINTS.userDetail(id));
  },
};

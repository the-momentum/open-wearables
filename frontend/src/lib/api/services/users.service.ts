import { apiClient } from '../client';
import { API_ENDPOINTS } from '../config';
import { appendSearchParams } from '@/lib/utils/url';
import type {
  UserRead,
  UserCreate,
  UserUpdate,
  UserQueryParams,
  PaginatedUsersResponse,
} from '../types';

export const usersService = {
  async getAll(params?: UserQueryParams): Promise<PaginatedUsersResponse> {
    const searchParams = new URLSearchParams();

    if (params) {
      appendSearchParams(searchParams, {
        page: params.page,
        limit: params.limit,
        sort_by: params.sort_by,
        sort_order: params.sort_order,
        search: params.search,
        email: params.email,
        external_user_id: params.external_user_id,
      });
    }

    const queryString = searchParams.toString();
    const url = queryString
      ? `${API_ENDPOINTS.users}?${queryString}`
      : API_ENDPOINTS.users;

    return apiClient.get<PaginatedUsersResponse>(url);
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

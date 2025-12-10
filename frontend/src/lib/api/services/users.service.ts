import { apiClient } from '../client';
import { API_ENDPOINTS } from '../config';
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

    if (params?.page != null) searchParams.set('page', params.page.toString());
    if (params?.limit != null) searchParams.set('limit', params.limit.toString());
    if (params?.sort_by) searchParams.set('sort_by', params.sort_by);
    if (params?.sort_order) searchParams.set('sort_order', params.sort_order);
    if (params?.search) searchParams.set('search', params.search);
    if (params?.email) searchParams.set('email', params.email);
    if (params?.external_user_id)
      searchParams.set('external_user_id', params.external_user_id);

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

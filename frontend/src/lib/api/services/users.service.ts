import { apiClient } from '../client';
import { API_ENDPOINTS } from '../config';
import { appendSearchParams } from '@/lib/utils/url';
import type {
  UserRead,
  UserCreate,
  UserUpdate,
  UserQueryParams,
  PaginatedUsersResponse,
  PresignedURLRequest,
  PresignedURLResponse,
  InvitationCode,
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

  async uploadAppleXml(userId: string, file: File): Promise<void> {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.postMultipart<void>(
      API_ENDPOINTS.userAppleXmlImport(userId),
      formData
    );
  },

  async getAppleXmlPresignedUrl(
    userId: string,
    request: PresignedURLRequest
  ): Promise<PresignedURLResponse> {
    return apiClient.post<PresignedURLResponse>(
      API_ENDPOINTS.userAppleXmlPresignedUrl(userId),
      request
    );
  },

  async uploadToS3(
    uploadUrl: string,
    formFields: Record<string, string>,
    file: File
  ): Promise<void> {
    const formData = new FormData();

    // Add all form fields first (AWS requires these before the file)
    Object.entries(formFields).forEach(([key, value]) => {
      formData.append(key, value);
    });

    // Add the file last
    formData.append('file', file);

    // Upload directly to S3 (no auth needed, using presigned URL)
    const response = await fetch(uploadUrl, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`S3 upload failed: ${response.statusText}`);
    }
  },

  async generateInvitationCode(userId: string): Promise<InvitationCode> {
    const endpoint = API_ENDPOINTS.userInvitationCode(userId);
    return apiClient.post<InvitationCode>(endpoint, null);
  },
};

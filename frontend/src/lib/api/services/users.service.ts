import { apiClient } from '../client';
import { API_ENDPOINTS, API_CONFIG } from '../config';
import { getToken, clearSession } from '@/lib/auth/session';
import { DEFAULT_REDIRECTS } from '@/lib/constants/routes';
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

  async uploadAppleXml(
    userId: string,
    file: File,
    onProgress?: (percent: number) => void
  ): Promise<void> {
    const formData = new FormData();
    formData.append('file', file);

    // Without a progress callback, keep the shared fetch path (401 handling, retries).
    if (!onProgress) {
      return apiClient.postMultipart<void>(
        API_ENDPOINTS.userAppleXmlImport(userId),
        formData
      );
    }

    const token = getToken();
    const url = `${API_CONFIG.baseUrl}${API_ENDPOINTS.userAppleXmlImport(userId)}`;
    const { status, statusText } = await uploadWithProgress(url, formData, {
      onProgress,
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      // This hits our authenticated backend, so treat a 401 like apiClient does.
      handleUnauthorized: true,
    });
    if (status < 200 || status >= 300) {
      throw new Error(`Upload failed (${status} ${statusText})`);
    }
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
    file: File,
    onProgress?: (percent: number) => void
  ): Promise<void> {
    const formData = new FormData();

    // Add all form fields first (S3 requires these before the file)
    Object.entries(formFields).forEach(([key, value]) => {
      formData.append(key, value);
    });

    // Add the file last
    formData.append('file', file);

    // Upload directly to S3 (no auth needed, using presigned URL). XHR is used
    // instead of fetch so upload progress can be reported.
    const { status, statusText } = await uploadWithProgress(
      uploadUrl,
      formData,
      {
        onProgress,
      }
    );

    if (status < 200 || status >= 300) {
      throw new Error(`S3 upload failed: ${status} ${statusText}`);
    }
  },

  async generateInvitationCode(userId: string): Promise<InvitationCode> {
    const endpoint = API_ENDPOINTS.userInvitationCode(userId);
    return apiClient.post<InvitationCode>(endpoint, null);
  },
};

interface UploadWithProgressOptions {
  onProgress?: (percent: number) => void;
  headers?: Record<string, string>;
  /**
   * When true, a 401 clears the session and redirects to login — mirroring
   * `apiClient`. Only enable for requests to our own authenticated backend;
   * a 401/403 from a presigned S3/MinIO URL is not an app-auth failure.
   */
  handleUnauthorized?: boolean;
}

/**
 * POST a FormData body via XMLHttpRequest so upload progress can be reported.
 * `fetch` cannot observe request-body upload progress, which is why this exists.
 * Resolves with the final status even for 4xx/5xx — callers decide how to react,
 * except a 401 with `handleUnauthorized` which triggers the shared re-login flow.
 */
function uploadWithProgress(
  url: string,
  formData: FormData,
  { onProgress, headers, handleUnauthorized }: UploadWithProgressOptions = {}
): Promise<{ status: number; statusText: string }> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', url);

    if (headers) {
      Object.entries(headers).forEach(([key, value]) => {
        xhr.setRequestHeader(key, value);
      });
    }

    if (onProgress) {
      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable) {
          onProgress(Math.round((event.loaded / event.total) * 100));
        }
      });
    }

    xhr.addEventListener('load', () => {
      if (handleUnauthorized && xhr.status === 401) {
        clearSession();
        if (typeof window !== 'undefined') {
          window.location.href = DEFAULT_REDIRECTS.unauthenticated;
        }
        reject(new Error('Session expired — please sign in again.'));
        return;
      }
      resolve({ status: xhr.status, statusText: xhr.statusText });
    });
    xhr.addEventListener('error', () =>
      reject(new Error('Network error during upload'))
    );
    xhr.addEventListener('abort', () => reject(new Error('Upload cancelled')));
    xhr.addEventListener('timeout', () =>
      reject(new Error('Upload timed out'))
    );

    xhr.send(formData);
  });
}

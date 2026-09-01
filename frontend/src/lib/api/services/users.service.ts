import { apiClient } from '../client';
import { API_ENDPOINTS, API_CONFIG } from '../config';
import { getToken, clearSession } from '@/lib/auth/session';
import { DEFAULT_REDIRECTS } from '@/lib/constants/routes';
import { appendSearchParams } from '@/lib/utils/url';
import {
  normalizeMultipartEtag,
  planMultipartParts,
  PART_UPLOAD_CONCURRENCY,
} from '@/lib/utils/multipart';
import { UPLOAD_REQUEST_TIMEOUT_MS } from '@/lib/constants/upload';
import type {
  UserRead,
  UserCreate,
  UserUpdate,
  UserQueryParams,
  PaginatedUsersResponse,
  PresignedURLRequest,
  PresignedURLResponse,
  MultipartCreateRequest,
  MultipartCreateResponse,
  MultipartSignRequest,
  MultipartSignResponse,
  MultipartCompleteRequest,
  MultipartCompleteResponse,
  MultipartAbortRequest,
  CompletedPart,
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

  async createMultipartUpload(
    userId: string,
    request: MultipartCreateRequest
  ): Promise<MultipartCreateResponse> {
    return apiClient.post<MultipartCreateResponse>(
      API_ENDPOINTS.userAppleXmlMultipartCreate(userId),
      request
    );
  },

  async signMultipartParts(
    userId: string,
    request: MultipartSignRequest
  ): Promise<MultipartSignResponse> {
    return apiClient.post<MultipartSignResponse>(
      API_ENDPOINTS.userAppleXmlMultipartSign(userId),
      request
    );
  },

  async completeMultipartUpload(
    userId: string,
    request: MultipartCompleteRequest
  ): Promise<MultipartCompleteResponse> {
    return apiClient.post<MultipartCompleteResponse>(
      API_ENDPOINTS.userAppleXmlMultipartComplete(userId),
      request
    );
  },

  async abortMultipartUpload(
    userId: string,
    request: MultipartAbortRequest
  ): Promise<void> {
    await apiClient.post<{ status: string }>(
      API_ENDPOINTS.userAppleXmlMultipartAbort(userId),
      request
    );
  },

  /**
   * Upload an Apple Health XML file to S3/MinIO using multipart upload.
   *
   * Works identically against AWS S3 and a self-hosted MinIO server. The file is
   * split into parts, each part is PUT directly to object storage via a presigned
   * URL, and the collected ETags are handed back to the backend to finalize the
   * object (which then dispatches processing in client-driven completion mode).
   */
  async uploadAppleXmlViaMultipart(
    userId: string,
    file: File,
    onProgress?: (percent: number) => void
  ): Promise<MultipartCompleteResponse> {
    const created = await this.createMultipartUpload(userId, {
      filename: file.name,
      content_type: file.type || 'application/xml',
      file_size: file.size,
    });
    let completionSubmitted = false;

    try {
      const plan = planMultipartParts(file.size, created.part_size);

      const { urls } = await this.signMultipartParts(userId, {
        key: created.key,
        upload_id: created.upload_id,
        part_numbers: plan.map((p) => p.partNumber),
      });
      const urlByPart = new Map(urls.map((u) => [u.part_number, u.url]));

      // Track uploaded bytes per part so overall progress reflects real throughput.
      const loadedPerPart = Array.from({ length: plan.length }, () => 0);
      const reportProgress = () => {
        if (!onProgress) return;
        const loaded = loadedPerPart.reduce((sum, n) => sum + n, 0);
        onProgress(
          file.size > 0 ? Math.round((loaded / file.size) * 100) : 100
        );
      };

      // Order-independent: the backend sorts parts by number before completing.
      const completedParts: CompletedPart[] = [];

      const uploadOne = async (index: number): Promise<void> => {
        const part = plan[index];
        const url = urlByPart.get(part.partNumber);
        if (!url) {
          throw new Error(`Missing presigned URL for part ${part.partNumber}`);
        }
        const blob = file.slice(part.start, part.end);
        const etag = await putPartWithProgress(url, blob, (loaded) => {
          loadedPerPart[index] = loaded;
          reportProgress();
        });
        loadedPerPart[index] = blob.size;
        reportProgress();
        completedParts.push({ part_number: part.partNumber, etag });
      };

      // Bounded-concurrency worker pool over the part indices.
      let nextIndex = 0;
      const worker = async (): Promise<void> => {
        while (nextIndex < plan.length) {
          const index = nextIndex;
          nextIndex += 1;
          await uploadOne(index);
        }
      };
      await Promise.all(
        Array.from(
          { length: Math.min(PART_UPLOAD_CONCURRENCY, plan.length) },
          () => worker()
        )
      );

      // Once this request starts, its outcome can be uncertain: the server may have
      // queued completion even if the response is lost. Do not race that worker with
      // an abort; the bucket lifecycle policy cleans up genuinely abandoned uploads.
      completionSubmitted = true;
      const result = await this.completeMultipartUpload(userId, {
        key: created.key,
        upload_id: created.upload_id,
        parts: completedParts,
      });
      onProgress?.(100);
      return result;
    } catch (error) {
      if (!completionSubmitted) {
        // Best-effort cleanup while no completion request can be in flight.
        await this.abortMultipartUpload(userId, {
          key: created.key,
          upload_id: created.upload_id,
        }).catch(() => undefined);
      }
      throw error;
    }
  },

  async generateInvitationCode(userId: string): Promise<InvitationCode> {
    const endpoint = API_ENDPOINTS.userInvitationCode(userId);
    return apiClient.post<InvitationCode>(endpoint, null);
  },
};

/**
 * PUT a single multipart part directly to object storage and resolve with its ETag.
 *
 * XHR is used (not fetch) so we can report byte-level upload progress. The ETag is
 * read from the response header, which requires the bucket's CORS policy to expose
 * `ETag` (see the MinIO/S3 setup docs).
 */
function putPartWithProgress(
  url: string,
  body: Blob,
  onProgress?: (loadedBytes: number) => void,
  timeoutMs = UPLOAD_REQUEST_TIMEOUT_MS
): Promise<string> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('PUT', url);
    xhr.timeout = timeoutMs;

    if (onProgress) {
      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable) onProgress(event.loaded);
      });
    }

    xhr.addEventListener('load', () => {
      if (xhr.status < 200 || xhr.status >= 300) {
        reject(
          new Error(`Part upload failed: ${xhr.status} ${xhr.statusText}`)
        );
        return;
      }
      const etag = xhr.getResponseHeader('ETag');
      if (!etag) {
        reject(
          new Error(
            'Object storage did not return an ETag. Ensure the bucket CORS policy exposes the ETag header.'
          )
        );
        return;
      }
      resolve(normalizeMultipartEtag(etag));
    });
    xhr.addEventListener('error', () =>
      reject(new Error('Network error during part upload'))
    );
    xhr.addEventListener('abort', () => reject(new Error('Upload cancelled')));
    xhr.addEventListener('timeout', () =>
      reject(new Error('Part upload timed out'))
    );

    xhr.send(body);
  });
}

interface UploadWithProgressOptions {
  onProgress?: (percent: number) => void;
  headers?: Record<string, string>;
  /**
   * When true, a 401 clears the session and redirects to login — mirroring
   * `apiClient`. Only enable for requests to our own authenticated backend;
   * a 401/403 from a presigned S3/MinIO URL is not an app-auth failure.
   */
  handleUnauthorized?: boolean;
  /** Finite request timeout; override for unusually slow deployments. */
  timeoutMs?: number;
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
  {
    onProgress,
    headers,
    handleUnauthorized,
    timeoutMs = UPLOAD_REQUEST_TIMEOUT_MS,
  }: UploadWithProgressOptions = {}
): Promise<{ status: number; statusText: string }> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', url);
    xhr.timeout = timeoutMs;

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

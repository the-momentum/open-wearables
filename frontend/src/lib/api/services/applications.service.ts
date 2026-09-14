import { apiClient } from '../client';
import { API_ENDPOINTS } from '../config';
import type {
  Application,
  ApplicationCreate,
  ApplicationWithSecret,
} from '../types';

export const applicationsService = {
  async list(): Promise<Application[]> {
    return apiClient.get<Application[]>(API_ENDPOINTS.applications);
  },

  async create(data: ApplicationCreate): Promise<ApplicationWithSecret> {
    return apiClient.post<ApplicationWithSecret>(
      API_ENDPOINTS.applications,
      data
    );
  },

  async delete(appId: string): Promise<void> {
    return apiClient.delete<void>(API_ENDPOINTS.applicationDetail(appId));
  },

  async rotateSecret(appId: string): Promise<ApplicationWithSecret> {
    return apiClient.post<ApplicationWithSecret>(
      API_ENDPOINTS.applicationRotateSecret(appId)
    );
  },
};

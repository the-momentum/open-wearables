import { apiClient } from '../client';
import { API_ENDPOINTS } from '../config';
import type { Developer } from '../types';

export const developersService = {
  async getDevelopers(): Promise<Developer[]> {
    return apiClient.get<Developer[]>(API_ENDPOINTS.developers);
  },

  async deleteDeveloper(id: string): Promise<void> {
    return apiClient.delete<void>(API_ENDPOINTS.developerDetail(id));
  },
};


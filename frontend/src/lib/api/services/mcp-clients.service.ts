import { apiClient } from '../client';
import { API_ENDPOINTS } from '../config';
import type { McpClient } from '../types';

export const mcpClientsService = {
  async list(): Promise<McpClient[]> {
    return apiClient.get<McpClient[]>(API_ENDPOINTS.mcpClients);
  },

  async forget(clientId: string): Promise<void> {
    return apiClient.delete<void>(API_ENDPOINTS.mcpClientDetail(clientId));
  },
};

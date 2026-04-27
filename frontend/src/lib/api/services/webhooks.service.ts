import { apiClient } from '../client';
import { API_ENDPOINTS } from '../config';
import type {
  WebhookAttemptsParams,
  WebhookEndpoint,
  WebhookEndpointCreate,
  WebhookEndpointSecret,
  WebhookEndpointUpdate,
  WebhookEventType,
  WebhookListResponse,
  WebhookMessage,
  WebhookMessageAttempt,
  WebhookTestEventResponse,
} from '../types';

export const webhooksService = {
  async listEventTypes(): Promise<WebhookEventType[]> {
    return apiClient.get<WebhookEventType[]>(API_ENDPOINTS.webhookEventTypes);
  },

  async list(): Promise<WebhookEndpoint[]> {
    return apiClient.get<WebhookEndpoint[]>(API_ENDPOINTS.webhookEndpoints);
  },

  async getById(id: string): Promise<WebhookEndpoint> {
    return apiClient.get<WebhookEndpoint>(
      API_ENDPOINTS.webhookEndpointDetail(id)
    );
  },

  async create(data: WebhookEndpointCreate): Promise<WebhookEndpoint> {
    return apiClient.post<WebhookEndpoint>(
      API_ENDPOINTS.webhookEndpoints,
      data
    );
  },

  async update(
    id: string,
    data: WebhookEndpointUpdate
  ): Promise<WebhookEndpoint> {
    return apiClient.patch<WebhookEndpoint>(
      API_ENDPOINTS.webhookEndpointDetail(id),
      data
    );
  },

  async delete(id: string): Promise<void> {
    return apiClient.delete<void>(API_ENDPOINTS.webhookEndpointDetail(id));
  },

  async getSecret(id: string): Promise<WebhookEndpointSecret> {
    return apiClient.get<WebhookEndpointSecret>(
      API_ENDPOINTS.webhookEndpointSecret(id)
    );
  },

  async sendTest(
    id: string,
    eventType?: string
  ): Promise<WebhookTestEventResponse> {
    return apiClient.post<WebhookTestEventResponse>(
      API_ENDPOINTS.webhookEndpointTest(id),
      eventType ? { event_type: eventType } : null
    );
  },

  async listMessages(): Promise<WebhookListResponse<WebhookMessage>> {
    return apiClient.get<WebhookListResponse<WebhookMessage>>(
      API_ENDPOINTS.webhookMessages
    );
  },

  async listAttempts(
    id: string,
    params?: WebhookAttemptsParams
  ): Promise<WebhookListResponse<WebhookMessageAttempt>> {
    return apiClient.get<WebhookListResponse<WebhookMessageAttempt>>(
      API_ENDPOINTS.webhookEndpointAttempts(id),
      { params: params as Record<string, unknown> }
    );
  },
};

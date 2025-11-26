import { apiClient } from '../client';
import { API_ENDPOINTS } from '../config';
import type { ApiKey, ApiKeyCreate } from '../types';

export const credentialsService = {
  async getApiKeys(): Promise<ApiKey[]> {
    return apiClient.get<ApiKey[]>(API_ENDPOINTS.apiKeys);
  },

  async getApiKey(id: string): Promise<ApiKey> {
    return apiClient.get<ApiKey>(API_ENDPOINTS.apiKeyDetail(id));
  },

  async createApiKey(data: ApiKeyCreate): Promise<ApiKey> {
    return apiClient.post<ApiKey>(API_ENDPOINTS.apiKeys, data);
  },

  async revokeApiKey(id: string): Promise<void> {
    return apiClient.delete<void>(API_ENDPOINTS.apiKeyDetail(id));
  },

  async deleteApiKey(id: string): Promise<void> {
    return apiClient.delete<void>(API_ENDPOINTS.apiKeyDetail(id));
  },

  getWidgetEmbedCode(
    apiKey: string,
    userId?: string
  ): { html: string; react: string } {
    const userParam = userId ? `&user_id=${userId}` : '';
    const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

    const html = `<!-- Open Wearables Connect Widget -->
<iframe
  src="${baseUrl}/widget/connect?api_key=${apiKey}${userParam}"
  width="600"
  height="400"
  frameborder="0"
  allow="clipboard-write"
  style="border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);"
></iframe>

<script>
  // Listen for connection success
  window.addEventListener('message', (event) => {
    if (event.data.type === 'wearable_connected') {
      console.log('Device connected:', event.data.provider)
      // Handle successful connection
    }
  })
</script>`;

    const react = `import { useEffect } from 'react'

function WearablesWidget() {
  useEffect(() => {
    // Listen for connection success
    const handleMessage = (event: MessageEvent) => {
      if (event.data.type === 'wearable_connected') {
        console.log('Device connected:', event.data.provider)
        // Handle successful connection
      }
    }

    window.addEventListener('message', handleMessage)
    return () => window.removeEventListener('message', handleMessage)
  }, [])

  return (
    <iframe
      src="${baseUrl}/widget/connect?api_key=${apiKey}${userParam}"
      width={600}
      height={400}
      frameBorder={0}
      allow="clipboard-write"
      style={{
        borderRadius: '8px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
      }}
    />
  )
}`;

    return { html, react };
  },
};

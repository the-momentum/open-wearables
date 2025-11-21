import { apiClient } from '../client';
import type { ApiKey, ApiKeyCreate } from '../types';
import { mockApiKeys } from '@/data/mock/credentials';

const USE_MOCK = import.meta.env.VITE_USE_MOCK_API === 'true';

// Helper to simulate API delay
const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export const credentialsService = {
  // List all API keys
  async getApiKeys(): Promise<ApiKey[]> {
    if (USE_MOCK) {
      await delay(300);
      return mockApiKeys;
    }
    return await apiClient.get<ApiKey[]>('/v1/credentials/api-keys');
  },

  // Get single API key
  async getApiKey(id: string): Promise<ApiKey> {
    if (USE_MOCK) {
      await delay(200);
      const apiKey = mockApiKeys.find((k) => k.id === id);
      if (!apiKey) {
        throw new Error(`API key ${id} not found`);
      }
      return apiKey;
    }
    return await apiClient.get<ApiKey>(`/v1/credentials/api-keys/${id}`);
  },

  // Create new API key
  async createApiKey(data: ApiKeyCreate): Promise<ApiKey> {
    if (USE_MOCK) {
      await delay(500);

      // Generate a random key
      const keyPrefix =
        data.type === 'widget'
          ? 'ow_widget_'
          : data.type === 'test'
            ? 'ow_test_'
            : 'ow_live_';
      const randomPart = Array.from({ length: 20 }, () =>
        '0123456789abcdefghijklmnopqrstuvwxyz'.charAt(
          Math.floor(Math.random() * 36)
        )
      ).join('');

      const newKey: ApiKey = {
        id: `key-${Date.now()}`,
        name: data.name,
        key: keyPrefix + randomPart,
        type: data.type,
        status: 'active',
        lastUsed: null,
        createdAt: new Date().toISOString(),
        expiresAt: null,
      };
      mockApiKeys.push(newKey);
      return newKey;
    }
    return await apiClient.post<ApiKey>('/v1/credentials/api-keys', data);
  },

  // Revoke/delete API key
  async revokeApiKey(id: string): Promise<void> {
    if (USE_MOCK) {
      await delay(300);
      const apiKey = mockApiKeys.find((k) => k.id === id);
      if (!apiKey) {
        throw new Error(`API key ${id} not found`);
      }
      apiKey.status = 'revoked';
      return;
    }
    await apiClient.delete(`/v1/credentials/api-keys/${id}`);
  },

  // Delete API key completely (for mock)
  async deleteApiKey(id: string): Promise<void> {
    if (USE_MOCK) {
      await delay(300);
      const index = mockApiKeys.findIndex((k) => k.id === id);
      if (index === -1) {
        throw new Error(`API key ${id} not found`);
      }
      mockApiKeys.splice(index, 1);
      return;
    }
    await apiClient.delete(`/v1/credentials/api-keys/${id}`);
  },

  // Get widget embed code
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

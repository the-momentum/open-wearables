export const API_CONFIG = {
  baseUrl: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  timeout: 30000, // 30 seconds
  retryAttempts: 3,
  retryDelay: 1000, // 1 second
} as const;

export const API_ENDPOINTS = {
  login: '/v1/auth/login',
  logout: '/v1/auth/logout',
  register: '/v1/auth/register',

  users: '/v1/users',
  userDetail: (id: string) => `/v1/users/${id}`,

  oauthAuthorize: (provider: string) => `/v1/oauth/${provider}/authorize`,
  oauthCallback: (provider: string) => `/v1/oauth/${provider}/callback`,

  heartRate: '/v1/heart-rate',
  sleep: '/v1/sleep',
  workouts: '/v1/workouts',

  apiKeys: '/v1/api-keys',
  apiKeyDetail: (id: string) => `/v1/api-keys/${id}`,

  automations: '/v1/automations',
  automationDetail: (id: string) => `/v1/automations/${id}`,
  testAutomation: (id: string) => `/v1/automations/${id}/test`,

  dashboardStats: '/v1/dashboard/stats',
  dashboardCharts: '/v1/dashboard/charts',

  requestLogs: '/v1/request-logs',

  chat: '/v1/chat',
} as const;

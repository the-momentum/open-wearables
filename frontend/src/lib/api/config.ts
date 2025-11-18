// API configuration

export const API_CONFIG = {
  baseUrl: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  timeout: 30000, // 30 seconds
  retryAttempts: 3,
  retryDelay: 1000, // 1 second
} as const;

export const API_ENDPOINTS = {
  // Auth
  login: '/v1/auth/login',
  logout: '/v1/auth/logout',
  register: '/v1/auth/register',

  // Users
  users: '/v1/users',
  userDetail: (id: string) => `/v1/users/${id}`,

  // OAuth
  oauthAuthorize: (provider: string) => `/v1/oauth/${provider}/authorize`,
  oauthCallback: (provider: string) => `/v1/oauth/${provider}/callback`,

  // Health Data
  heartRate: '/v1/heart-rate',
  sleep: '/v1/sleep',
  workouts: '/v1/workouts',

  // API Keys
  apiKeys: '/v1/api-keys',
  apiKeyDetail: (id: string) => `/v1/api-keys/${id}`,

  // Automations
  automations: '/v1/automations',
  automationDetail: (id: string) => `/v1/automations/${id}`,
  testAutomation: (id: string) => `/v1/automations/${id}/test`,

  // Dashboard
  dashboardStats: '/v1/dashboard/stats',
  dashboardCharts: '/v1/dashboard/charts',

  // Request Logs
  requestLogs: '/v1/request-logs',

  // AI Chat
  chat: '/v1/chat',
} as const;

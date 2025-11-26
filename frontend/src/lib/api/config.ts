export const API_CONFIG = {
  baseUrl: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  timeout: 30000, // 30 seconds
  retryAttempts: 3,
  retryDelay: 1000, // 1 second
} as const;

export const API_ENDPOINTS = {
  login: '/api/v1/auth/login',
  logout: '/api/v1/auth/logout',
  register: '/api/v1/auth/register',
  forgotPassword: '/api/v1/auth/forgot-password',
  resetPassword: '/api/v1/auth/reset-password',

  users: '/api/v1/users',
  userDetail: (id: string) => `/api/v1/users/${id}`,

  oauthAuthorize: (provider: string) => `/api/v1/oauth/${provider}/authorize`,
  oauthCallback: (provider: string) => `/api/v1/oauth/${provider}/callback`,

  heartRate: '/api/v1/heart-rate',
  sleep: '/api/v1/sleep',
  workouts: '/api/v1/workouts',

  apiKeys: '/api/v1/api-keys',
  apiKeyDetail: (id: string) => `/api/v1/api-keys/${id}`,

  automations: '/api/v1/automations',
  automationDetail: (id: string) => `/api/v1/automations/${id}`,
  testAutomation: (id: string) => `/api/v1/automations/${id}/test`,

  dashboardStats: '/api/v1/dashboard/stats',
  dashboardCharts: '/api/v1/dashboard/charts',

  requestLogs: '/api/v1/request-logs',

  chat: '/api/v1/chat',
} as const;

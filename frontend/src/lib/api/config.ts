export const API_CONFIG = {
  baseUrl: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  timeout: 30000, // 30 seconds
  retryAttempts: 3,
  retryDelay: 1000, // 1 second
} as const;

export const API_ENDPOINTS = {
  // Auth endpoints
  login: '/api/v1/auth/login',
  logout: '/api/v1/auth/logout',
  register: '/api/v1/auth/register',
  me: '/api/v1/auth/me',
  forgotPassword: '/api/v1/auth/forgot-password',
  resetPassword: '/api/v1/auth/reset-password',

  // User endpoints
  users: '/api/v1/users',
  userDetail: (id: string) => `/api/v1/users/${id}`,
  userHeartRate: (userId: string) => `/api/v1/users/${userId}/heart-rate`,
  userWorkouts: (userId: string) => `/api/v1/users/${userId}/workouts`,

  // OAuth endpoints
  oauthAuthorize: (provider: string) => `/api/v1/oauth/${provider}/authorize`,
  oauthCallback: (provider: string) => `/api/v1/oauth/${provider}/callback`,
  oauthSuccess: '/api/v1/oauth/success',
  oauthProviders: '/api/v1/oauth/providers',

  // API Keys endpoints
  apiKeys: '/api/v1/developer/api-keys',
  apiKeyDetail: (id: string) => `/api/v1/developer/api-keys/${id}`,
  apiKeyRotate: (id: string) => `/api/v1/developer/api-keys/${id}/rotate`,

  // Vendor workouts endpoints
  vendorWorkouts: (provider: string, userId: string) =>
    `/api/v1/vendors/${provider}/users/${userId}/workouts`,
  vendorWorkoutDetail: (provider: string, userId: string, workoutId: string) =>
    `/api/v1/vendors/${provider}/users/${userId}/workouts/${workoutId}`,

  // Dashboard endpoints (may not exist in backend yet)
  dashboardStats: '/api/v1/dashboard/stats',
  dashboardCharts: '/api/v1/dashboard/charts',

  // Automations endpoints (may not exist in backend yet)
  automations: '/api/v1/automations',
  automationDetail: (id: string) => `/api/v1/automations/${id}`,
  testAutomation: (id: string) => `/api/v1/automations/${id}/test`,
} as const;

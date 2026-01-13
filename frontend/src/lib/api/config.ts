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
  userConnections: (userId: string) => `/api/v1/users/${userId}/connections`,
  userWorkouts: (userId: string) => `/api/v1/users/${userId}/events/workouts`,
  userAppleXmlImport: (userId: string) =>
    `/api/v1/users/${userId}/import/apple/xml/direct`,
  userAppleXmlPresignedUrl: (userId: string) =>
    `/api/v1/users/${userId}/import/apple/xml/s3`,

  // OAuth endpoints
  oauthAuthorize: (provider: string) => `/api/v1/oauth/${provider}/authorize`,
  oauthCallback: (provider: string) => `/api/v1/oauth/${provider}/callback`,
  oauthSuccess: '/api/v1/oauth/success',
  oauthProviders: '/api/v1/oauth/providers',

  // API Keys endpoints
  apiKeys: '/api/v1/developer/api-keys',
  apiKeyDetail: (id: string) => `/api/v1/developer/api-keys/${id}`,
  apiKeyRotate: (id: string) => `/api/v1/developer/api-keys/${id}/rotate`,

  // Provider workouts endpoints
  providerSynchronization: (provider: string, userId: string) =>
    `/api/v1/providers/${provider}/users/${userId}/sync`,
  providerWorkouts: (provider: string, userId: string) =>
    `/api/v1/providers/${provider}/users/${userId}/workouts`,
  providerWorkoutDetail: (
    provider: string,
    userId: string,
    workoutId: string
  ) => `/api/v1/providers/${provider}/users/${userId}/workouts/${workoutId}`,

  // Dashboard endpoints (may not exist in backend yet)
  dashboardStats: '/api/v1/dashboard/stats',
  dashboardCharts: '/api/v1/dashboard/charts',

  // Automations endpoints (may not exist in backend yet)
  automations: '/api/v1/automations',
  automationDetail: (id: string) => `/api/v1/automations/${id}`,
  testAutomation: (id: string) => `/api/v1/automations/${id}/test`,

  // Developers endpoints
  developers: '/api/v1/developers',
  developerDetail: (id: string) => `/api/v1/developers/${id}`,

  // Invitations endpoints (authenticated)
  invitations: '/api/v1/invitations',
  invitationDetail: (id: string) => `/api/v1/invitations/${id}`,
  invitationResend: (id: string) => `/api/v1/invitations/${id}/resend`,

  // Accept invitation (public - no auth)
  acceptInvitation: '/api/v1/invitations/accept',

  // Summary endpoints (authenticated - requires user authorization)
  userActivitySummary: (userId: string) =>
    `/api/v1/users/${userId}/summaries/activity`,
  userSleepSummary: (userId: string) =>
    `/api/v1/users/${userId}/summaries/sleep`,
  userBodySummary: (userId: string) => `/api/v1/users/${userId}/summaries/body`,
  userRecoverySummary: (userId: string) =>
    `/api/v1/users/${userId}/summaries/recovery`,
} as const;

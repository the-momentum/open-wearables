export const ROUTES = {
  // Public routes
  login: '/login',
  register: '/register',
  forgotPassword: '/forgot-password',
  resetPassword: '/reset-password',
  acceptInvite: '/accept-invite',

  // Authenticated routes
  dashboard: '/dashboard',
  users: '/users',
  settings: '/settings',

  // Widget routes
  widgetConnect: '/widget/connect',
} as const;

export const DEFAULT_REDIRECTS = {
  authenticated: ROUTES.dashboard,
  unauthenticated: ROUTES.login,
} as const;

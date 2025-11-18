// Session management utilities

const TOKEN_KEY = 'ow_auth_token';
const DEVELOPER_ID_KEY = 'ow_developer_id';
const SESSION_EXPIRY_KEY = 'ow_session_expiry';

const DEFAULT_SESSION_DURATION = 24 * 60 * 60 * 1000; // 24 hours

export interface Session {
  token: string;
  developerId: string;
  expiresAt: number;
}

/**
 * Store session data
 */
export function setSession(
  token: string,
  developerId: string,
  expiresIn?: number
): void {
  const expiresAt = Date.now() + (expiresIn || DEFAULT_SESSION_DURATION);

  if (typeof window !== 'undefined') {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(DEVELOPER_ID_KEY, developerId);
    localStorage.setItem(SESSION_EXPIRY_KEY, expiresAt.toString());
  }
}

/**
 * Get current session
 */
export function getSession(): Session | null {
  if (typeof window === 'undefined') {
    return null;
  }

  const token = localStorage.getItem(TOKEN_KEY);
  const developerId = localStorage.getItem(DEVELOPER_ID_KEY);
  const expiresAt = localStorage.getItem(SESSION_EXPIRY_KEY);

  if (!token || !developerId || !expiresAt) {
    return null;
  }

  // Check if session is expired
  if (Date.now() > parseInt(expiresAt, 10)) {
    clearSession();
    return null;
  }

  return {
    token,
    developerId,
    expiresAt: parseInt(expiresAt, 10),
  };
}

/**
 * Get auth token
 */
export function getToken(): string | null {
  const session = getSession();
  return session?.token || null;
}

/**
 * Get developer ID
 */
export function getDeveloperId(): string | null {
  const session = getSession();
  return session?.developerId || null;
}

/**
 * Check if user is authenticated
 */
export function isAuthenticated(): boolean {
  return getSession() !== null;
}

/**
 * Clear session data
 */
export function clearSession(): void {
  if (typeof window !== 'undefined') {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(DEVELOPER_ID_KEY);
    localStorage.removeItem(SESSION_EXPIRY_KEY);
  }
}

/**
 * Check if session is about to expire (within 5 minutes)
 */
export function isSessionExpiringSoon(): boolean {
  const session = getSession();
  if (!session) return false;

  const fiveMinutes = 5 * 60 * 1000;
  return session.expiresAt - Date.now() < fiveMinutes;
}

/**
 * Get time until session expires (in milliseconds)
 */
export function getTimeUntilExpiry(): number {
  const session = getSession();
  if (!session) return 0;

  return Math.max(0, session.expiresAt - Date.now());
}

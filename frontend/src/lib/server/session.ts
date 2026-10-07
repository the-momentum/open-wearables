import type { Cookies } from '@sveltejs/kit';
import { refreshTokens, revokeToken, type Developer, type TokenResponse } from './api';

export const SESSION_COOKIE = 'ow_session';

const SESSION_TTL_SECONDS = 60 * 60 * 24 * 30;
/** Refresh early so a request cannot race the expiry. */
const REFRESH_SKEW_MS = 60_000;
const FALLBACK_ACCESS_TOKEN_TTL_SECONDS = 3600;
/** How long a rotation stays answerable for requests still carrying the old cookie. */
const ROTATION_GRACE_MS = 30_000;

export type Session = {
	accessToken: string;
	refreshToken: string | null;
	/** Epoch milliseconds. */
	accessTokenExpiresAt: number;
	/** Captured at sign-in; goes stale if edited elsewhere. */
	developer: Developer;
};

export function sessionFromTokens(
	tokens: TokenResponse,
	developer: Developer,
	now = Date.now()
): Session {
	const ttl = tokens.expires_in ?? FALLBACK_ACCESS_TOKEN_TTL_SECONDS;
	return {
		accessToken: tokens.access_token,
		refreshToken: tokens.refresh_token,
		accessTokenExpiresAt: now + ttl * 1000,
		developer
	};
}

export function needsRefresh(session: Session, now = Date.now()): boolean {
	return now >= session.accessTokenExpiresAt - REFRESH_SKEW_MS;
}

export const encodeSession = (session: Session) =>
	Buffer.from(JSON.stringify(session)).toString('base64url');

export function decodeSession(raw: string | undefined): Session | null {
	if (!raw) return null;
	try {
		const session = JSON.parse(Buffer.from(raw, 'base64url').toString()) as Session;
		return typeof session.accessToken === 'string' && session.developer ? session : null;
	} catch {
		return null;
	}
}

// HttpOnly keeps the tokens out of reach of any script on the page.
function store(cookies: Cookies, session: Session): void {
	cookies.set(SESSION_COOKIE, encodeSession(session), {
		path: '/',
		httpOnly: true,
		sameSite: 'lax',
		maxAge: SESSION_TTL_SECONDS
	});
}

const clear = (cookies: Cookies) => cookies.delete(SESSION_COOKIE, { path: '/' });

export function createSession(cookies: Cookies, tokens: TokenResponse, developer: Developer): void {
	store(cookies, sessionFromTokens(tokens, developer));
}

export const readSession = (cookies: Cookies): Session | null =>
	decodeSession(cookies.get(SESSION_COOKIE));

const rotations = new Map<string, Promise<TokenResponse>>();

/**
 * The backend revokes a refresh token the moment it is used, so two requests
 * refreshing with the same one would sign the second out. They share one call
 * instead, and a request that arrives just after still gets its answer.
 */
export function rotate(refreshToken: string): Promise<TokenResponse> {
	let pending = rotations.get(refreshToken);
	if (!pending) {
		pending = refreshTokens(refreshToken);
		rotations.set(refreshToken, pending);
		// Only a success is kept: a failed call must not answer the next attempt.
		pending.then(
			() => setTimeout(() => rotations.delete(refreshToken), ROTATION_GRACE_MS),
			() => rotations.delete(refreshToken)
		);
	}
	return pending;
}

/**
 * Refreshes when due. Null once the session cannot be renewed, and the caller
 * should treat the user as signed out.
 */
export async function validAccessToken(cookies: Cookies, session: Session): Promise<string | null> {
	if (!needsRefresh(session)) return session.accessToken;
	if (!session.refreshToken) return null;

	try {
		const renewed = sessionFromTokens(await rotate(session.refreshToken), session.developer);
		store(cookies, renewed);
		return renewed.accessToken;
	} catch {
		clear(cookies);
		return null;
	}
}

export async function destroySession(cookies: Cookies): Promise<void> {
	const existing = readSession(cookies);
	clear(cookies);
	if (existing?.refreshToken) await revokeToken(existing.refreshToken);
}

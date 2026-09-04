import type { Cookies } from '@sveltejs/kit';
import { redis } from './redis';
import { refreshTokens, revokeToken, type Developer, type TokenResponse } from './api';

export const SESSION_COOKIE = 'ow_session';

const SESSION_TTL_SECONDS = 60 * 60 * 24 * 30;
/** Refresh early so a request cannot race the expiry. */
const REFRESH_SKEW_MS = 60_000;
const FALLBACK_ACCESS_TOKEN_TTL_SECONDS = 3600;

export type Session = {
	accessToken: string;
	refreshToken: string | null;
	/** Epoch milliseconds. */
	accessTokenExpiresAt: number;
	/** Captured at sign-in; goes stale if edited elsewhere. */
	developer: Developer;
};

export type SessionRecord = { id: string; session: Session };

const sessionKey = (id: string) => `ow:sess:${id}`;

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

async function store(id: string, session: Session): Promise<void> {
	await redis().set(sessionKey(id), JSON.stringify(session), 'EX', SESSION_TTL_SECONDS);
}

export async function createSession(
	cookies: Cookies,
	tokens: TokenResponse,
	developer: Developer
): Promise<void> {
	const id = crypto.randomUUID();
	await store(id, sessionFromTokens(tokens, developer));

	cookies.set(SESSION_COOKIE, id, {
		path: '/',
		httpOnly: true,
		sameSite: 'lax',
		maxAge: SESSION_TTL_SECONDS
	});
}

/** Null means "not signed in" — including when Redis is unreachable. */
export async function readSession(cookies: Cookies): Promise<SessionRecord | null> {
	const id = cookies.get(SESSION_COOKIE);
	if (!id) return null;

	try {
		const raw = await redis().get(sessionKey(id));
		return raw ? { id, session: JSON.parse(raw) as Session } : null;
	} catch {
		return null;
	}
}

/**
 * Refreshes when due. Null once the session cannot be renewed, and the caller
 * should treat the user as signed out.
 */
export async function validAccessToken({ id, session }: SessionRecord): Promise<string | null> {
	if (!needsRefresh(session)) return session.accessToken;
	if (!session.refreshToken) return null;

	try {
		// The backend rotates, so the whole response must be persisted.
		const renewed = sessionFromTokens(await refreshTokens(session.refreshToken), session.developer);
		await store(id, renewed);
		return renewed.accessToken;
	} catch {
		await redis()
			.del(sessionKey(id))
			.catch(() => {});
		return null;
	}
}

export async function destroySession(cookies: Cookies): Promise<void> {
	const existing = await readSession(cookies);
	cookies.delete(SESSION_COOKIE, { path: '/' });
	if (!existing) return;

	if (existing.session.refreshToken) await revokeToken(existing.session.refreshToken);
	await redis()
		.del(sessionKey(existing.id))
		.catch(() => {});
}

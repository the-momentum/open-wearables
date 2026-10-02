import type { Cookies } from '@sveltejs/kit';
import { readSession, validAccessToken, type SessionRecord } from './session';

export type AuthContext = {
	session(): Promise<SessionRecord | null>;
	accessToken(): Promise<string | null>;
};

/**
 * Lazy and memoised per request: the layout guard and the page load both run
 * for one render, and neither should cause a second Redis read or a second
 * token refresh.
 */
export function createAuthContext(cookies: Cookies): AuthContext {
	let session: Promise<SessionRecord | null> | undefined;
	let token: Promise<string | null> | undefined;

	const getSession = () => (session ??= readSession(cookies));

	return {
		session: getSession,
		accessToken: () =>
			(token ??= getSession().then((record) => (record ? validAccessToken(record) : null)))
	};
}

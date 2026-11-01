import type { Cookies } from '@sveltejs/kit';
import { readSession, validAccessToken, type Session } from './session';

export type AuthContext = {
	session(): Session | null;
	accessToken(): Promise<string | null>;
};

/** The layout guard and the page load both ask for a token; only the first may refresh it. */
export function createAuthContext(cookies: Cookies): AuthContext {
	let token: Promise<string | null> | undefined;

	return {
		session: () => readSession(cookies),
		accessToken: () => {
			const session = readSession(cookies);
			return (token ??= session ? validAccessToken(cookies, session) : Promise.resolve(null));
		}
	};
}

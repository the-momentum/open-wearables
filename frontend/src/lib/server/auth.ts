import { redirect, type Cookies } from '@sveltejs/kit';
import { resolve } from '$app/paths';
import { clearSession, readSession, renewSession, validAccessToken, type Session } from './session';

export type AuthContext = {
	session(): Session | null;
	accessToken(): Promise<string | null>;
	/** The renewed token, null for a token this session never held, or a redirect to sign-in. */
	rejected(token: string): Promise<string | null>;
};

/** The layout guard and the page load both ask for a token; only the first may refresh it. */
export function createAuthContext(cookies: Cookies): AuthContext {
	let token: Promise<string | null> | undefined;
	// One renewal per request: a page's parallel calls all fail with the same token.
	let renewal: { from: string; to: Promise<string> } | undefined;

	async function signedOut(): Promise<never> {
		// A cookie left behind would send /login straight back to the dashboard.
		clearSession(cookies);
		redirect(303, resolve('/login'));
	}

	return {
		session: () => readSession(cookies),
		accessToken: () => {
			const session = readSession(cookies);
			return (token ??= session ? validAccessToken(cookies, session) : Promise.resolve(null));
		},
		rejected: async (refused) => {
			if (renewal) {
				if (refused === renewal.from) return renewal.to;
				// The renewed token was refused too, so another refresh would not help.
				if (refused === (await renewal.to)) return signedOut();
				return null;
			}

			// A token the session does not hold - a sign-in still in progress, say.
			const session = readSession(cookies);
			if (session?.accessToken !== refused) return null;

			const to = renewSession(cookies, session).then((renewed) => renewed ?? signedOut());
			renewal = { from: refused, to };
			token = to;
			return to;
		}
	};
}

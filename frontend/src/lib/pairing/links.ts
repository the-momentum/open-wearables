/** The page an end user opens to connect a provider; `token` is what lets them in. */
export function pairingPath(userId: string, token: string): string {
	return `/users/${userId}/pair?${new URLSearchParams({ t: token })}`;
}

export function pairingLink(origin: string, userId: string, token: string): string {
	return `${origin.replace(/\/+$/, '')}${pairingPath(userId, token)}`;
}

/**
 * Browser side: the dashboard server mints the token, since only it holds the session.
 * The origin is the browser's: behind a proxy the server's own may be wrong.
 */
export async function fetchPairingLink(userId: string): Promise<string> {
	const response = await fetch(`/users/${userId}/pair-link`, { method: 'POST' });
	if (!response.ok) throw new Error(`Could not create a pairing link (${response.status})`);
	const { token } = (await response.json()) as { token: string };
	return pairingLink(location.origin, userId, token);
}

/** Lets the success page offer "Connect another device" without the token touching the API's URLs. */
export const PAIR_TOKEN_COOKIE = 'pair_token';

/** The pairing link is public, so its query string is attacker-controlled. */
export function safeReturnUrl(raw: string | null): string | null {
	if (!raw) return null;

	try {
		const url = new URL(raw);
		return url.protocol === 'http:' || url.protocol === 'https:' ? url.toString() : null;
	} catch {
		return null;
	}
}

export function pairingSuccessUrl(
	origin: string,
	userId: string,
	provider: string,
	returnUrl: string | null
): string {
	const target = new URL(`/users/${userId}/pair/success`, origin);
	target.searchParams.set('provider', provider);

	const back = safeReturnUrl(returnUrl);
	if (back) target.searchParams.set('redirect_url', back);

	return target.toString();
}

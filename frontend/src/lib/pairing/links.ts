/** The page an end user opens to connect a provider; `token` is what lets them in. */
export function pairingPath(userId: string, token: string): string {
	return `/users/${userId}/pair?${new URLSearchParams({ t: token })}`;
}

export function pairingLink(origin: string, userId: string, token: string): string {
	return `${origin.replace(/\/+$/, '')}${pairingPath(userId, token)}`;
}

/** Browser side: asks the dashboard server to mint a link, since only it holds the session. */
export async function fetchPairingLink(userId: string): Promise<string> {
	const response = await fetch(`/users/${userId}/pair-link`, { method: 'POST' });
	if (!response.ok) throw new Error(`Could not create a pairing link (${response.status})`);
	return ((await response.json()) as { url: string }).url;
}

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
	returnUrl: string | null,
	token: string
): string {
	const target = new URL(`/users/${userId}/pair/success`, origin);
	target.searchParams.set('provider', provider);
	// Carried so "Connect another device" can reopen the pairing page.
	target.searchParams.set('t', token);

	const back = safeReturnUrl(returnUrl);
	if (back) target.searchParams.set('redirect_url', back);

	return target.toString();
}

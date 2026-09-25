/** The page an end user opens to connect a provider; lives on this frontend. */
export function pairingPath(userId: string): string {
	return `/users/${userId}/pair`;
}

export function pairingLink(origin: string, userId: string): string {
	return `${origin.replace(/\/+$/, '')}${pairingPath(userId)}`;
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
	returnUrl: string | null
): string {
	const target = new URL(`${pairingPath(userId)}/success`, origin);
	target.searchParams.set('provider', provider);

	const back = safeReturnUrl(returnUrl);
	if (back) target.searchParams.set('redirect_url', back);

	return target.toString();
}

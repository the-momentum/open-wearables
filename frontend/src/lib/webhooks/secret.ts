/** Browser side: the dashboard server asks the API, since only it holds the session. */
export async function fetchSigningSecret(id: string): Promise<string> {
	const response = await fetch(`/webhooks/${id}/secret`, { cache: 'no-store' });
	if (!response.ok) throw new Error(`Could not load the signing secret (${response.status})`);
	const { key } = (await response.json()) as { key: string };
	return key;
}

/** Svix secrets all start `whsec_`, so the prefix says what it is without giving anything away. */
export const MASKED_SECRET = `whsec_${'•'.repeat(24)}`;

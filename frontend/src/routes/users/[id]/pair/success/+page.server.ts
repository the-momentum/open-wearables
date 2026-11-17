import { fetchCloudProviders } from '$lib/server/providers';
import { providerLabel } from '$lib/providers/labels';
import { PAIR_TOKEN_COOKIE, pairingPath, safeReturnUrl } from '$lib/pairing/links';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params, url, cookies }) => {
	const slug = url.searchParams.get('provider') ?? '';
	const token = cookies.get(PAIR_TOKEN_COOKIE);

	return {
		connected: url.searchParams.get('status') === 'success',
		message: url.searchParams.get('message'),
		provider: slug ? providerLabel(await fetchCloudProviders(), slug) : null,
		returnUrl: safeReturnUrl(url.searchParams.get('redirect_url')),
		pairAnother: token ? pairingPath(params.id, token) : null
	};
};

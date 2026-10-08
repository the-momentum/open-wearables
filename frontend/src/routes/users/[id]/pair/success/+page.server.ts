import { fetchCloudProviders } from '$lib/server/providers';
import { providerLabel } from '$lib/providers/labels';
import { pairingPath, safeReturnUrl } from '$lib/pairing/links';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params, url }) => {
	const slug = url.searchParams.get('provider') ?? '';

	return {
		provider: slug ? providerLabel(await fetchCloudProviders(), slug) : null,
		returnUrl: safeReturnUrl(url.searchParams.get('redirect_url')),
		pairAnother: pairingPath(params.id)
	};
};

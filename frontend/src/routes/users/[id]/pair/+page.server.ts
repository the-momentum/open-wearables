import { fail, redirect } from '@sveltejs/kit';
import { ApiError } from '$lib/server/api';
import { authorizeProvider } from '$lib/server/oauth';
import { fetchCloudProviders } from '$lib/server/providers';
import { pairingSuccessUrl, safeReturnUrl } from '$lib/pairing/links';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ url }) => ({
	providers: await fetchCloudProviders(),
	returnUrl: safeReturnUrl(url.searchParams.get('redirect_url'))
});

export const actions: Actions = {
	connect: async ({ params, request, url }) => {
		// `?/connect` replaces the query string, so the return link travels as a field.
		const form = await request.formData();
		const provider = String(form.get('provider') ?? '');
		const returnUrl = String(form.get('return_url') ?? '') || null;

		let authorizationUrl: string;
		try {
			const target = pairingSuccessUrl(url.origin, params.id, provider, returnUrl);
			({ authorization_url: authorizationUrl } = await authorizeProvider(
				provider,
				params.id,
				target
			));
		} catch (error) {
			const detail = error instanceof ApiError ? error.message : 'Try again in a moment.';
			return fail(400, { provider, message: `Could not reach ${provider}. ${detail}` });
		}

		redirect(303, authorizationUrl);
	}
};

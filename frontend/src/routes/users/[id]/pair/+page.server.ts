import { fail, redirect } from '@sveltejs/kit';
import { ApiError } from '$lib/server/api';
import { authorizeProvider } from '$lib/server/oauth';
import { fetchCloudProviders } from '$lib/server/providers';
import { pairingSuccessUrl, safeReturnUrl } from '$lib/pairing/links';
import type { Actions, PageServerLoad } from './$types';

const invalidLink = 'This link has expired or is invalid. Ask whoever sent it for a new one.';

export const load: PageServerLoad = async ({ url }) => ({
	providers: await fetchCloudProviders(),
	returnUrl: safeReturnUrl(url.searchParams.get('redirect_url')),
	token: url.searchParams.get('t'),
	invalidLink
});

export const actions: Actions = {
	connect: async ({ params, request, url }) => {
		// `?/connect` replaces the query string, so the return link and token travel as fields.
		const form = await request.formData();
		const provider = String(form.get('provider') ?? '');
		const returnUrl = String(form.get('return_url') ?? '') || null;
		const token = String(form.get('token') ?? '');

		if (!token) return fail(401, { provider, message: invalidLink });

		let authorizationUrl: string;
		try {
			const target = pairingSuccessUrl(url.origin, params.id, provider, returnUrl, token);
			({ authorization_url: authorizationUrl } = await authorizeProvider(
				provider,
				params.id,
				target,
				token
			));
		} catch (error) {
			if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
				return fail(401, { provider, message: invalidLink });
			}
			const detail = error instanceof ApiError ? error.message : 'Try again in a moment.';
			return fail(400, { provider, message: `Could not reach ${provider}. ${detail}` });
		}

		redirect(303, authorizationUrl);
	}
};

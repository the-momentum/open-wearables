import { fail, redirect } from '@sveltejs/kit';
import { ApiError } from '$lib/server/api';
import { authorizeProvider } from '$lib/server/oauth';
import { fetchCloudProviders } from '$lib/server/providers';
import { PAIR_TOKEN_COOKIE, pairingSuccessUrl, safeReturnUrl } from '$lib/pairing/links';
import type { Actions, PageServerLoad } from './$types';

const invalidLink = 'This link has expired or is invalid. Ask whoever sent it for a new one.';

export const load: PageServerLoad = async ({ url }) => ({
	providers: await fetchCloudProviders(),
	returnUrl: safeReturnUrl(url.searchParams.get('redirect_url')),
	token: url.searchParams.get('t'),
	invalidLink
});

export const actions: Actions = {
	connect: async ({ params, request, url, cookies }) => {
		// `?/connect` replaces the query string, so the return link travels as a field.
		const form = await request.formData();
		const provider = String(form.get('provider') ?? '');
		const returnUrl = String(form.get('return_url') ?? '') || null;
		const token = url.searchParams.get('t') ?? '';

		if (!token) return fail(401, { provider, message: invalidLink });

		let authorizationUrl: string;
		try {
			const target = pairingSuccessUrl(url.origin, params.id, provider, returnUrl);
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

		// Not in the success URL: that is sent to the API as redirect_uri and could reach its logs.
		cookies.set(PAIR_TOKEN_COOKIE, token, {
			path: `/users/${params.id}/pair`,
			httpOnly: true,
			sameSite: 'lax',
			maxAge: 60 * 60
		});
		redirect(303, authorizationUrl);
	}
};

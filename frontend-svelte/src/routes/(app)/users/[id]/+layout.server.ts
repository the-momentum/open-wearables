import { error } from '@sveltejs/kit';
import { ApiError } from '$lib/server/api';
import { requireToken } from '$lib/server/guard';
import { fetchUserDetail } from '$lib/server/users';
import type { LayoutServerLoad } from './$types';

/** Every tab needs the user; only this load fetches it. */
export const load: LayoutServerLoad = async ({ params, locals }) => {
	const accessToken = await requireToken(locals);

	try {
		return { user: await fetchUserDetail(params.id, accessToken) };
	} catch (cause) {
		if (cause instanceof ApiError && cause.status === 404) error(404, 'User not found');
		throw cause;
	}
};

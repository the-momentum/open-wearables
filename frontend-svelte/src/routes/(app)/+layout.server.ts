import { redirect } from '@sveltejs/kit';
import { resolve } from '$app/paths';
import type { LayoutServerLoad } from './$types';

/** A revoked session surfaces at the next refresh, not instantly — the trade a
 *  short access token exists to make, and it keeps /auth/me off every render. */
export const load: LayoutServerLoad = async ({ locals }) => {
	const record = await locals.auth.session();
	if (!record) redirect(303, resolve('/login'));

	if (!(await locals.auth.accessToken())) redirect(303, resolve('/login'));

	return { developer: record.session.developer };
};

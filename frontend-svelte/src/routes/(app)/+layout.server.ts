import { redirect } from '@sveltejs/kit';
import { resolve } from '$app/paths';
import { readSession, validAccessToken } from '$lib/server/session';
import type { LayoutServerLoad } from './$types';

/** A revoked session surfaces at the next refresh, not instantly — the trade a
 *  short access token exists to make, and it keeps /auth/me off every render. */
export const load: LayoutServerLoad = async ({ cookies }) => {
	const record = await readSession(cookies);
	if (!record) redirect(303, resolve('/login'));

	const accessToken = await validAccessToken(record);
	if (!accessToken) redirect(303, resolve('/login'));

	return { developer: record.session.developer };
};

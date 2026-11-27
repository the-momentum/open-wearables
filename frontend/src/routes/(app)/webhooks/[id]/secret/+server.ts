import { json } from '@sveltejs/kit';
import { requireToken } from '$lib/server/guard';
import { getSigningSecret } from '$lib/server/webhooks';
import type { RequestHandler } from './$types';

/**
 * One subscription's signing secret, fetched only when someone asks to see or
 * copy it. Kept out of the page load so it is not in the markup of every visit,
 * and out of any cache on the way back.
 */
export const GET: RequestHandler = async ({ params, locals }) => {
	const accessToken = await requireToken(locals);
	const { key } = await getSigningSecret(params.id, accessToken);

	return json({ key }, { headers: { 'cache-control': 'no-store' } });
};

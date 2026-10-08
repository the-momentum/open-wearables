import { json } from '@sveltejs/kit';
import { requireToken } from '$lib/server/guard';
import { listDeliveries } from '$lib/server/webhooks';
import type { RequestHandler } from './$types';

/**
 * The last few deliveries for one subscription, fetched when its row opens.
 * With the list loading them for every row it would be one Svix round trip per
 * subscription for the rows nobody expands.
 */
export const GET: RequestHandler = async ({ params, locals }) => {
	const accessToken = await requireToken(locals);

	return json(await listDeliveries(params.id, accessToken, { limit: 5 }));
};

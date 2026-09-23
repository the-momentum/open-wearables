import { json } from '@sveltejs/kit';
import { requireToken } from '$lib/server/guard';
import { fetchStoredRun } from '$lib/server/syncs';
import type { RequestHandler } from './$types';

/**
 * The stored record of one run, asked for when its row opens: a list of five
 * hundred would otherwise read Postgres five hundred times for rows nobody opens.
 */
export const GET: RequestHandler = async ({ params, locals }) => {
	const accessToken = await requireToken(locals);
	return json({ stored: await fetchStoredRun(params.run, accessToken) });
};

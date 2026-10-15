import { json } from '@sveltejs/kit';
import { requireToken } from '$lib/server/guard';
import { fetchStoredRun } from '$lib/server/syncs';
import type { RequestHandler } from './$types';

/** Fetched when a row opens, not for the whole list. */
export const GET: RequestHandler = async ({ params, locals }) => {
	const accessToken = await requireToken(locals);
	return json({ stored: await fetchStoredRun(params.run, accessToken) });
};

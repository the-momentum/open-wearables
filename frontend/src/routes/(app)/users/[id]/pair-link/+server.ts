import { json } from '@sveltejs/kit';
import { requireToken } from '$lib/server/guard';
import { mintConnectToken } from '$lib/server/oauth';
import type { RequestHandler } from './$types';

/** A fresh token per copy; the browser builds the link around it. */
export const POST: RequestHandler = async ({ params, locals }) => {
	const accessToken = await requireToken(locals);
	const { token } = await mintConnectToken(params.id, accessToken);

	return json({ token });
};

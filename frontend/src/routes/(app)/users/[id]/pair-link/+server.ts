import { json } from '@sveltejs/kit';
import { requireToken } from '$lib/server/guard';
import { mintConnectToken } from '$lib/server/oauth';
import { pairingLink } from '$lib/pairing/links';
import type { RequestHandler } from './$types';

/** A fresh pairing link per copy: the token in it is what lets the end user connect. */
export const POST: RequestHandler = async ({ params, locals, url }) => {
	const accessToken = await requireToken(locals);
	const { token } = await mintConnectToken(params.id, accessToken);

	return json({ url: pairingLink(url.origin, params.id, token) });
};

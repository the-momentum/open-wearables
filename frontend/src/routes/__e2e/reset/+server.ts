import { error } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import { forgetAll } from '$lib/server/cache';
import type { RequestHandler } from './$types';

// The cache lives in this process, so the suite resets it here, between tests.
export const POST: RequestHandler = () => {
	if (env.OW_E2E !== '1') error(404);
	forgetAll();
	return new Response(null, { status: 204 });
};

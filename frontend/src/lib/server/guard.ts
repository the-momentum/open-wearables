import { redirect } from '@sveltejs/kit';
import { resolve } from '$app/paths';

/**
 * Loads and actions run concurrently with the layout guard, so neither can
 * assume it ran.
 */
export async function requireToken(locals: App.Locals): Promise<string> {
	const accessToken = await locals.auth.accessToken();
	if (!accessToken) redirect(303, resolve('/login'));
	return accessToken;
}

import type { Handle } from '@sveltejs/kit';
import { createAuthContext } from '$lib/server/auth';

export const handle: Handle = async ({ event, resolve }) => {
	event.locals.auth = createAuthContext(event.cookies);
	return resolve(event);
};

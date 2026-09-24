import type { Handle } from '@sveltejs/kit';
import { createAuthContext } from '$lib/server/auth';
import { parseTheme, THEME_COOKIE, themeClass } from '$lib/theme';

export const handle: Handle = async ({ event, resolve }) => {
	event.locals.auth = createAuthContext(event.cookies);
	event.locals.theme = parseTheme(event.cookies.get(THEME_COOKIE));

	// Rendered into <html> so a chosen theme is there before the first paint.
	return resolve(event, {
		transformPageChunk: ({ html }) => html.replace('%ow.theme%', themeClass(event.locals.theme))
	});
};

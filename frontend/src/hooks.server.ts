import type { Handle, ServerInit } from '@sveltejs/kit';
import { createAuthContext } from '$lib/server/auth';
import { getBranding } from '$lib/server/branding';
import { parseTheme, THEME_COOKIE, themeClass } from '$lib/theme';

// Validates INSTANCE_BRANDING before the first request, so a bad value is logged at startup.
export const init: ServerInit = () => {
	getBranding();
};

export const handle: Handle = async ({ event, resolve }) => {
	event.locals.auth = createAuthContext(event.cookies);
	event.locals.theme = parseTheme(event.cookies.get(THEME_COOKIE));

	// Rendered into <html> so a chosen theme is there before the first paint.
	return resolve(event, {
		transformPageChunk: ({ html }) => html.replace('%ow.theme%', themeClass(event.locals.theme))
	});
};

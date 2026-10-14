import { env } from '$env/dynamic/public';
import { parseBranding, type Branding } from '$lib/branding';

let cached: Branding | undefined;

/** Read and validated once per server process: changing it means a redeploy. */
export const getBranding = (): Branding =>
	(cached ??= parseBranding(env.VITE_BRANDING, (message) => console.warn(`[branding] ${message}`)));

const escapeAttribute = (value: string) =>
	value.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

const FAVICON_BLOCK = /<!-- ow:favicon -->[\s\S]*?<!-- \/ow:favicon -->/;

/** Swaps app.html's bundled favicons for the configured one, if any. */
export const applyFavicon = (html: string, faviconUrl: string | undefined) =>
	faviconUrl
		? html.replace(FAVICON_BLOCK, `<link rel="icon" href="${escapeAttribute(faviconUrl)}" />`)
		: html;

import { env } from '$env/dynamic/private';
import { parseBranding, type Branding } from '$lib/branding/branding';

let cached: Branding | undefined;

/** Read and validated once per server process: changing it means a redeploy. */
export const getBranding = (): Branding =>
	(cached ??= parseBranding(env.INSTANCE_BRANDING, (message) =>
		console.warn(`[branding] ${message}`)
	));

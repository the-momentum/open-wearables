import { getBranding } from '$lib/server/branding';
import type { LayoutServerLoad } from './$types';

export const load: LayoutServerLoad = ({ locals }) => {
	const { name, faviconUrl } = getBranding();
	return { theme: locals.theme, brandName: name, faviconUrl };
};

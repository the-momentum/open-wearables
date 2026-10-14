import { getBranding } from '$lib/server/branding';
import type { LayoutServerLoad } from './$types';

export const load: LayoutServerLoad = ({ locals }) => ({
	theme: locals.theme,
	brandName: getBranding().name
});

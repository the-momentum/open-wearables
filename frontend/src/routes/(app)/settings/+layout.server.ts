import { readFeatures } from '$lib/server/config';
import { requireToken } from '$lib/server/guard';
import type { LayoutServerLoad } from './$types';

export const load: LayoutServerLoad = async ({ locals }) => ({
	features: await readFeatures(await requireToken(locals))
});

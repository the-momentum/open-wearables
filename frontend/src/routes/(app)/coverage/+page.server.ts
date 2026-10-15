import { requireToken } from '$lib/server/guard';
import { fetchCoverage } from '$lib/server/coverage';
import { fetchProviders } from '$lib/server/providers';
import { LAYERS, type Layer } from '$lib/coverage/rows';
import type { PageServerLoad } from './$types';

/**
 * Two static requests and no user data at all: the matrix is built from the
 * provider strategies in code, and the catalogue names them. Nothing here grows
 * with anything.
 */
export const load: PageServerLoad = async ({ url, locals }) => {
	const accessToken = await requireToken(locals);

	const asked = (key: string) => url.searchParams.get(key) ?? '';

	const [coverage, providers] = await Promise.all([
		fetchCoverage(accessToken),
		fetchProviders(accessToken)
	]);

	return {
		coverage,
		providers,
		filters: {
			search: asked('search').trim(),
			layer: (asked('layer') in LAYERS ? asked('layer') : '') as Layer | '',
			// Only what the matrix knows: anything else narrows to nothing and reads
			// as a fault rather than a typo.
			provider: coverage.providers.includes(asked('provider')) ? asked('provider') : '',
			missing: asked('missing') === '1'
		}
	};
};

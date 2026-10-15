import { requireToken } from '$lib/server/guard';
import { fetchAllProviders } from '$lib/server/providers';
import { listDeviceTypePriorities, listProviderPriorities } from '$lib/server/settings';
import { fetchDataSources } from '$lib/server/sources';
import { userActions } from '$lib/server/user-actions';
import { groupByProvider, rankSources } from '$lib/sources/sources';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params, locals }) => {
	const accessToken = await requireToken(locals);

	// Every provider, not just the enabled ones: a source outlives its provider being switched off
	const [providers, sources, providerPriorities, deviceTypePriorities] = await Promise.all([
		fetchAllProviders(accessToken),
		fetchDataSources(params.id, accessToken),
		listProviderPriorities(accessToken),
		listDeviceTypePriorities(accessToken)
	]);

	return {
		providers,
		groups: groupByProvider(rankSources(sources, providerPriorities, deviceTypePriorities))
	};
};

/** The header sits in the layout, so its actions have to exist on every tab. */
export const actions = userActions as Actions;

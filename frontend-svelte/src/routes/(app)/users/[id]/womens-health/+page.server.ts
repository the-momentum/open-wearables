import { attempt } from '$lib/server/form';
import { deleteCycle, fetchCycles } from '$lib/server/cycles';
import { requireToken } from '$lib/server/guard';
import { fetchProviders } from '$lib/server/providers';
import { userActions } from '$lib/server/user-actions';
import { isPageSize } from '$lib/lists/pagination';
import type { Actions, PageServerLoad } from './$types';

/**
 * No period and no provider control. This endpoint drops the upper bound of the
 * window on purpose — a cycle running now ends in the future — so a range would
 * narrow one end of it and silently not the other.
 */
export const load: PageServerLoad = async ({ params, url, locals }) => {
	const accessToken = await requireToken(locals);
	const cursor = url.searchParams.get('cursor') ?? '';

	// Ten, not the list default of twenty: these cards expand, and a person has
	// thirteen cycles a year, so ten is most of one.
	const asked = Number(url.searchParams.get('size'));
	const pageSize = isPageSize(asked) ? asked : 10;

	const [providers, cycles] = await Promise.all([
		fetchProviders(accessToken),
		fetchCycles(params.id, accessToken, { cursor, limit: pageSize })
	]);

	return { cycles, providers, pageSize };
};

export const actions: Actions = {
	// The header sits in the layout, so its actions have to exist on every tab.
	...userActions,

	deleteCycle: async ({ params, request, locals }) => {
		const accessToken = await requireToken(locals);
		const id = String((await request.formData()).get('cycle') ?? '');

		return attempt('deleteCycle', { cycle: id }, () => deleteCycle(params.id, id, accessToken));
	}
};

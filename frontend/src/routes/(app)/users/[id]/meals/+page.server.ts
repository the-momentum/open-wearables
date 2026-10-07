import { attempt } from '$lib/server/form';
import { userActions } from '$lib/server/user-actions';
import { fetchConnections } from '$lib/server/connections';
import { requireToken } from '$lib/server/guard';
import { knownProvider } from '$lib/server/events';
import { deleteMeal, fetchMeals } from '$lib/server/meals';
import { fetchProviders } from '$lib/server/providers';
import { parsePeriod } from '$lib/filters/period';
import { isPageSize } from '$lib/lists/pagination';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params, url, locals }) => {
	const accessToken = await requireToken(locals);
	const period = parsePeriod(url.searchParams);

	const askedProvider = url.searchParams.get('provider') ?? '';
	const cursor = url.searchParams.get('cursor') ?? '';

	const asked = Number(url.searchParams.get('size'));
	const pageSize = isPageSize(asked) ? asked : 10;

	const options = Promise.all([
		fetchProviders(accessToken),
		fetchConnections(params.id, accessToken)
	]);

	const query = (provider: string) =>
		fetchMeals(params.id, accessToken, { period, provider, cursor, limit: pageSize });

	const started = askedProvider ? null : query('');

	const [providers, connections] = await options;
	const provider = knownProvider(connections, askedProvider);

	const meals = (await started) ?? (await query(provider));

	return { period, provider, meals, providers, connections, pageSize };
};

export const actions: Actions = {
	...userActions,

	deleteMeal: async ({ params, request, locals }) => {
		const accessToken = await requireToken(locals);
		const id = String((await request.formData()).get('meal') ?? '');

		return attempt('deleteMeal', { meal: id }, () => deleteMeal(params.id, id, accessToken));
	}
};

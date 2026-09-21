import { attempt } from '$lib/server/form';
import { fetchConnections } from '$lib/server/connections';
import { requireToken } from '$lib/server/guard';
import { knownProvider } from '$lib/server/events';
import { fetchProviders } from '$lib/server/providers';
import { deleteSleep, fetchSleep } from '$lib/server/sleep';
import { parsePeriod } from '$lib/filters/period';
import { isPageSize } from '$lib/lists/pagination';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params, url, locals }) => {
	const accessToken = await requireToken(locals);
	const period = parsePeriod(url.searchParams);

	const askedProvider = url.searchParams.get('provider') ?? '';
	const topSourceOnly = url.searchParams.get('top') === '1';
	const cursor = url.searchParams.get('cursor') ?? '';

	// Ten, not the list default of twenty: these cards expand, and twenty of them
	// is a page nobody reaches the end of. The sizes on offer are the shared ones.
	const asked = Number(url.searchParams.get('size'));
	const pageSize = isPageSize(asked) ? asked : 10;

	// Connections, not the period's own providers: a filter that vanishes as you
	// step through days is worse than no filter.
	const options = Promise.all([
		fetchProviders(accessToken),
		fetchConnections(params.id, accessToken)
	]);

	const query = (provider: string) =>
		fetchSleep(params.id, accessToken, {
			period,
			provider,
			topSourceOnly,
			cursor,
			limit: pageSize
		});

	// With no provider asked for there is nothing to check, so the list query
	// travels alongside the option lists instead of queueing behind them.
	const started = askedProvider ? null : query('');

	const [providers, connections] = await options;
	const provider = knownProvider(connections, askedProvider);

	const sessions = (await started) ?? (await query(provider));

	return { period, provider, topSourceOnly, sessions, providers, connections, pageSize };
};

export const actions: Actions = {
	deleteSleep: async ({ params, request, locals }) => {
		const accessToken = await requireToken(locals);
		const id = String((await request.formData()).get('session') ?? '');

		return attempt('deleteSleep', { session: id }, () => deleteSleep(params.id, id, accessToken));
	}
};

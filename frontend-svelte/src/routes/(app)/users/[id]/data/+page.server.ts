import { fetchConnections } from '$lib/server/connections';
import { requireToken } from '$lib/server/guard';
import { fetchProviders } from '$lib/server/providers';
import { fetchDataSummary, fetchDataTimeline } from '$lib/server/summary';
import { parsePeriod } from '$lib/summary/period';
import type { PageServerLoad } from './$types';

/**
 * Both aggregates scan this user's slice of data_point_series, which is why
 * Data Summary is its own route: opening a user to check an email must not pay
 * for them.
 */
export const load: PageServerLoad = async ({ params, url, locals }) => {
	const accessToken = await requireToken(locals);
	const period = parsePeriod(url.searchParams);

	// Connections, not the period's own providers: a filter that vanishes as you
	// step through days is worse than no filter.
	const [summary, byType, byProvider, providers, connections] = await Promise.all([
		fetchDataSummary(params.id, accessToken, period),
		fetchDataTimeline(params.id, accessToken, period, 'series_type'),
		fetchDataTimeline(params.id, accessToken, period, 'provider'),
		fetchProviders(accessToken),
		fetchConnections(params.id, accessToken)
	]);

	return { period, summary, byType, byProvider, providers, connections };
};

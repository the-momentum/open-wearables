import { fetchConnections } from '$lib/server/connections';
import { requireToken } from '$lib/server/guard';
import { fetchProviders } from '$lib/server/providers';
import { fetchDataSummary, fetchDataTimeline } from '$lib/server/summary';
import { parsePeriod } from '$lib/filters/period';
import type { TimelineGroupBy } from '$lib/summary/types';
import { userActions } from '$lib/server/user-actions';
import type { Actions, PageServerLoad } from './$types';

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
	const [providers, connections] = await Promise.all([
		fetchProviders(accessToken),
		fetchConnections(params.id, accessToken)
	]);

	// A provider this user has no connection to is a typo, not a filter. The API
	// takes a ProviderName enum, so passing one through would 422 the timelines
	// and take the whole page down with them.
	const asked = url.searchParams.get('provider') ?? '';
	const provider = connections.some((connection) => connection.provider === asked) ? asked : '';

	const timeline = (groupBy: TimelineGroupBy) =>
		fetchDataTimeline(params.id, accessToken, period, groupBy, provider);

	const [summary, byType, byProvider, byWorkout] = await Promise.all([
		fetchDataSummary(params.id, accessToken, period),
		timeline('series_type'),
		timeline('provider'),
		timeline('workout_type')
	]);

	return { period, provider, summary, byType, byProvider, byWorkout, providers, connections };
};

/** The header sits in the layout, so its actions have to exist on every tab. */
export const actions = userActions as Actions;

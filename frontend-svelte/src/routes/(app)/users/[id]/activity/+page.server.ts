import { fetchActivity } from '$lib/server/activity';
import { fetchProviders } from '$lib/server/providers';
import { requireToken } from '$lib/server/guard';
import { parsePeriod } from '$lib/filters/period';
import { isPageSize } from '$lib/lists/pagination';
import type { PageServerLoad } from './$types';

/**
 * No provider filter and no delete: this endpoint aggregates the time series by
 * date and keeps the highest-priority source per day before it answers, so there
 * is one row per day and nothing here anyone can remove.
 */
export const load: PageServerLoad = async ({ params, url, locals }) => {
	const accessToken = await requireToken(locals);
	const period = parsePeriod(url.searchParams);
	const cursor = url.searchParams.get('cursor') ?? '';

	// Ten, not the list default of twenty: these cards expand, and twenty of them
	// is a page nobody reaches the end of. The sizes on offer are the shared ones.
	const asked = Number(url.searchParams.get('size'));
	const pageSize = isPageSize(asked) ? asked : 10;

	// Nothing to validate, so both travel together.
	const [providers, days] = await Promise.all([
		fetchProviders(accessToken),
		fetchActivity(params.id, accessToken, { period, cursor, limit: pageSize })
	]);

	return { period, days, providers, pageSize };
};

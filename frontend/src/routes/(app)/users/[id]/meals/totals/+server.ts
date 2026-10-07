import { json } from '@sveltejs/kit';
import { parsePeriod } from '$lib/filters/period';
import { sumMeals } from '$lib/meals/totals';
import { fetchConnections } from '$lib/server/connections';
import { knownProvider, SUMMARY_CAP } from '$lib/server/events';
import { requireToken } from '$lib/server/guard';
import { fetchMeals } from '$lib/server/meals';
import type { RequestHandler } from './$types';

// No totals endpoint for meals, so the period's meals are summed here, up to one capped page.
export const GET: RequestHandler = async ({ params, url, locals }) => {
	const accessToken = await requireToken(locals);
	const asked = url.searchParams.get('provider') ?? '';
	const provider = asked
		? knownProvider(await fetchConnections(params.id, accessToken), asked)
		: '';

	const page = await fetchMeals(params.id, accessToken, {
		period: parsePeriod(url.searchParams),
		provider,
		limit: SUMMARY_CAP
	});

	return json(sumMeals(page.data, page.pagination.total_count, page.pagination.has_more));
};

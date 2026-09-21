import { json } from '@sveltejs/kit';
import { SUMMARY_CAP } from '$lib/server/events';
import { requireToken } from '$lib/server/guard';
import { fetchWorkouts } from '$lib/server/workouts';
import { parsePeriod } from '$lib/filters/period';
import { sumWorkouts } from '$lib/workouts/totals';
import type { RequestHandler } from './$types';

/**
 * Its own request because there is no workout aggregate to ask: the figures are
 * summed from every record in the period, which is far more than the list needs
 * and would otherwise hold the cards back behind it.
 */
export const GET: RequestHandler = async ({ params, url, locals }) => {
	const accessToken = await requireToken(locals);

	const page = await fetchWorkouts(params.id, accessToken, {
		period: parsePeriod(url.searchParams),
		provider: url.searchParams.get('provider') ?? '',
		type: url.searchParams.get('type') ?? '',
		limit: SUMMARY_CAP,
		zones: false
	});

	return json(sumWorkouts(page.data, page.pagination.total_count));
};

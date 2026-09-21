import { json } from '@sveltejs/kit';
import { parsePeriod } from '$lib/filters/period';
import { SUMMARY_CAP } from '$lib/server/events';
import { requireToken } from '$lib/server/guard';
import { fetchSleep } from '$lib/server/sleep';
import { sumSleep } from '$lib/sleep/totals';
import type { RequestHandler } from './$types';

/**
 * Its own request because there is no sleep aggregate to ask: the figures are
 * summed from every session in the period, which is far more than the list needs
 * and would otherwise hold the cards back behind it.
 */
export const GET: RequestHandler = async ({ params, url, locals }) => {
	const accessToken = await requireToken(locals);

	const page = await fetchSleep(params.id, accessToken, {
		period: parsePeriod(url.searchParams),
		provider: url.searchParams.get('provider') ?? '',
		topSourceOnly: url.searchParams.get('top') === '1',
		limit: SUMMARY_CAP,
		stages: false
	});

	return json(sumSleep(page.data, page.pagination.total_count));
};

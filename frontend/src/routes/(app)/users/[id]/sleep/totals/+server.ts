import { json } from '@sveltejs/kit';
import { fetchSleepTotals } from '$lib/server/sleep';
import { requireToken } from '$lib/server/guard';
import { parsePeriod } from '$lib/filters/period';
import { sessionFilter } from '$lib/sleep/query';
import { toSleepTotals } from '$lib/sleep/totals';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ params, url, locals }) => {
	const accessToken = await requireToken(locals);
	const totals = await fetchSleepTotals(params.id, accessToken, {
		period: parsePeriod(url.searchParams),
		provider: url.searchParams.get('provider') ?? '',
		topSourceOnly: url.searchParams.get('top') === '1',
		kind: sessionFilter(url.searchParams)
	});
	return json(toSleepTotals(totals));
};

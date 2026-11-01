import { json } from '@sveltejs/kit';
import { fetchActivityTotals } from '$lib/server/activity';
import { requireToken } from '$lib/server/guard';
import { parsePeriod } from '$lib/filters/period';
import { toActivityTotals } from '$lib/activity/totals';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ params, url, locals }) => {
	const accessToken = await requireToken(locals);
	const totals = await fetchActivityTotals(params.id, accessToken, parsePeriod(url.searchParams));
	return json(toActivityTotals(totals));
};

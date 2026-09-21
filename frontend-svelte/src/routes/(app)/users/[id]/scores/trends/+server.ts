import { json } from '@sveltejs/kit';
import { requireToken } from '$lib/server/guard';
import { fetchScoreHistory } from '$lib/server/scores';
import { parsePeriod } from '$lib/filters/period';
import type { RequestHandler } from './$types';

/**
 * Every category at once, whatever the list below is narrowed to: the trends
 * are how a category is chosen, so filtering them would empty the chooser.
 */
export const GET: RequestHandler = async ({ params, url, locals }) => {
	const accessToken = await requireToken(locals);
	const history = await fetchScoreHistory(params.id, accessToken, parsePeriod(url.searchParams));

	return json({ scores: history.data, truncated: history.pagination.has_more });
};

import { json } from '@sveltejs/kit';
import { sumCycles } from '$lib/cycles/totals';
import { fetchCycles } from '$lib/server/cycles';
import { SUMMARY_CAP } from '$lib/server/events';
import { requireToken } from '$lib/server/guard';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ params, locals }) => {
	const accessToken = await requireToken(locals);
	const page = await fetchCycles(params.id, accessToken, { limit: SUMMARY_CAP });

	return json(sumCycles(page.data, page.pagination.total_count, page.pagination.has_more));
};

import { json } from '@sveltejs/kit';
import { fetchWorkoutTotals } from '$lib/server/workouts';
import { requireToken } from '$lib/server/guard';
import { parsePeriod } from '$lib/filters/period';
import { toWorkoutTotals } from '$lib/workouts/totals';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ params, url, locals }) => {
	const accessToken = await requireToken(locals);
	const totals = await fetchWorkoutTotals(params.id, accessToken, {
		period: parsePeriod(url.searchParams),
		provider: url.searchParams.get('provider') ?? '',
		type: url.searchParams.get('type') ?? ''
	});
	return json(toWorkoutTotals(totals));
};

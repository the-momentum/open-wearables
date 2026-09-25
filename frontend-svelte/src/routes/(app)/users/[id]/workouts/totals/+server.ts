import { json } from '@sveltejs/kit';
import { summaryOf } from '$lib/server/events';
import { fetchWorkouts } from '$lib/server/workouts';
import { requireToken } from '$lib/server/guard';
import { sumWorkouts } from '$lib/workouts/totals';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ params, url, locals }) => {
	const accessToken = await requireToken(locals);

	return json(
		await summaryOf(
			url,
			(period, limit) =>
				fetchWorkouts(params.id, accessToken, {
					period,
					limit,
					provider: url.searchParams.get('provider') ?? '',
					type: url.searchParams.get('type') ?? '',
					zones: false
				}),
			sumWorkouts
		)
	);
};

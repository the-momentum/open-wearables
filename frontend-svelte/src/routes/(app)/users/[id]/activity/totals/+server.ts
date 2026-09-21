import { json } from '@sveltejs/kit';
import { summaryOf } from '$lib/server/events';
import { fetchActivity } from '$lib/server/activity';
import { requireToken } from '$lib/server/guard';
import { sumActivity } from '$lib/activity/totals';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ params, url, locals }) => {
	const accessToken = await requireToken(locals);

	return json(
		await summaryOf(
			url,
			(period, limit) =>
				fetchActivity(params.id, accessToken, {
					period,
					limit
				}),
			sumActivity
		)
	);
};

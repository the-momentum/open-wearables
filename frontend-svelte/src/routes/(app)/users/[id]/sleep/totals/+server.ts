import { json } from '@sveltejs/kit';
import { summaryOf } from '$lib/server/events';
import { fetchSleep } from '$lib/server/sleep';
import { requireToken } from '$lib/server/guard';
import { sumSleep } from '$lib/sleep/totals';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ params, url, locals }) => {
	const accessToken = await requireToken(locals);

	return json(
		await summaryOf(
			url,
			(period, limit) =>
				fetchSleep(params.id, accessToken, {
					period,
					limit,
					provider: url.searchParams.get('provider') ?? '',
					topSourceOnly: url.searchParams.get('top') === '1',
					stages: false
				}),
			sumSleep
		)
	);
};

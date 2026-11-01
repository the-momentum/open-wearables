import { json } from '@sveltejs/kit';
import { requireToken } from '$lib/server/guard';
import { fetchSamples, NO_SAMPLES, samplesFor } from '$lib/server/timeseries';
import { ACTIVITY_TYPES } from '$lib/timeseries/samples';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ params, url, locals }) => {
	const accessToken = await requireToken(locals);
	const asked = samplesFor(url, ACTIVITY_TYPES);
	if (!asked) return json(NO_SAMPLES);

	return json(await fetchSamples(params.id, accessToken, asked.window, asked.provider));
};

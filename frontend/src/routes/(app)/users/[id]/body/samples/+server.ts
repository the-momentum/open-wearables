import { json } from '@sveltejs/kit';
import { requireToken } from '$lib/server/guard';
import { fetchSamples, NO_SAMPLES, samplesFor } from '$lib/server/timeseries';
import { VITAL_TYPES } from '$lib/timeseries/samples';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ params, url, locals }) => {
	const accessToken = await requireToken(locals);
	const asked = samplesFor(url, VITAL_TYPES);
	if (!asked) return json(NO_SAMPLES);

	// A vital is a day value for most providers (Oura's resting pulse, Whoop's nightly HRV), and the
	// raw stream no longer carries those; the day rows hold every device's, ours where the provider sent none.
	return json(await fetchSamples(params.id, accessToken, asked.window, asked.provider, '1day'));
};

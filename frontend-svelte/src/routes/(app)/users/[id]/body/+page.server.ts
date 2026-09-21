import { fetchBody } from '$lib/server/body';
import { requireToken } from '$lib/server/guard';
import { fetchProviders } from '$lib/server/providers';
import { defaultRange, parsePeriod, periodWindow } from '$lib/filters/period';
import type { PageServerLoad } from './$types';

/**
 * A snapshot, not a list: `/summaries/body` answers with one object and no
 * pagination. The period drives the trends underneath it, which come from the
 * time series instead.
 */
export const load: PageServerLoad = async ({ params, url, locals }) => {
	const accessToken = await requireToken(locals);

	// The trends need bounds, and "all time" would ask for a decade of readings
	// to draw a line nobody can read. A window is the honest default here.
	const asked = parsePeriod(url.searchParams);
	const period = asked.from ? asked : defaultRange();

	const [providers, body] = await Promise.all([
		fetchProviders(accessToken),
		fetchBody(params.id, accessToken)
	]);

	return { period, window: periodWindow(period), body, providers };
};

import { redirect } from '@sveltejs/kit';
import { requireToken } from '$lib/server/guard';
import { fetchProviders } from '$lib/server/providers';
import { fetchScoreDays, scoreDays } from '$lib/server/scores';
import { userActions } from '$lib/server/user-actions';
import { parsePeriod } from '$lib/filters/period';
import { isPageSize } from '$lib/lists/pagination';
import { knownCategory } from '$lib/scores/categories';
import { dayCount, dayPages, dayWindow } from '$lib/scores/paging';
import { withParams } from '$lib/utils/url';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params, url, locals }) => {
	const accessToken = await requireToken(locals);
	const period = parsePeriod(url.searchParams);

	// Unknown categories are dropped rather than forwarded: the API takes an enum
	// and 422s the whole page on anything else.
	const asked = url.searchParams.get('category') ?? '';
	const category = knownCategory(asked) ? asked : '';

	// Ten days, not the list default of twenty: a day card carries a row per
	// measure and expands, and twenty of them is a page nobody reaches the end
	// of. The sizes on offer are the shared ones.
	const size = Number(url.searchParams.get('size'));
	const perPage = isPageSize(size) ? size : 10;
	const at = Math.max(Math.trunc(Number(url.searchParams.get('page'))) || 1, 1);

	// The providers travel alongside: nothing about them decides the window.
	const [providers, window] = await Promise.all([
		fetchProviders(accessToken),
		scoreDays(params.id, accessToken, period)
	]);

	// A stale deep link, or a size change made against a shorter period, would
	// otherwise render a window that falls outside it entirely.
	const pages = dayPages(window, perPage);
	if (at > pages) redirect(303, withParams(url, { page: pages === 1 ? null : String(pages) }));

	const scores = await fetchScoreDays(
		params.id,
		accessToken,
		dayWindow(window, at, perPage),
		category
	);

	return {
		period,
		category,
		scores,
		providers,
		page: at,
		pages,
		perPage,
		total: dayCount(window),
		/** Whether the reader narrowed anything, which shapes the empty state. */
		narrowed: Boolean(category) || period.from !== null
	};
};

/** The header sits in the layout, so its actions have to exist on every tab. */
export const actions = userActions as Actions;

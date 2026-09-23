import { requireToken } from '$lib/server/guard';
import { fetchProviders } from '$lib/server/providers';
import { fetchRunWindow, forgetRunWindow } from '$lib/server/syncs';
import { DEFAULT_PAGE_SIZE, isPageSize } from '$lib/lists/pagination';
import { overview, pageOf, runFilters, SYNC_WINDOW } from '$lib/syncs/runs';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ url, locals }) => {
	const accessToken = await requireToken(locals);
	const filters = runFilters(url.searchParams);

	const asked = Number(url.searchParams.get('size'));
	const size = isPageSize(asked) ? asked : DEFAULT_PAGE_SIZE;

	const [buffer, providers] = await Promise.all([
		fetchRunWindow(filters, accessToken),
		fetchProviders(accessToken)
	]);

	const { page, rows } = pageOf(buffer.runs, Number(url.searchParams.get('page')) || 1, size);

	return {
		filters,
		providers,
		runs: rows,
		page,
		size,
		total: buffer.runs.length,
		// A full window means there were more than it holds in the last 24 hours.
		capped: buffer.runs.length >= SYNC_WINDOW,
		overview: overview(buffer.runs),
		fetchedAt: buffer.fetchedAt
	};
};

export const actions: Actions = {
	// The filters arrive as fields: `?/refresh` replaces the query string, so the
	// page's own would not reach this action.
	refresh: async ({ request }) => {
		const form = await request.formData();
		const fields = new URLSearchParams();
		for (const [name, value] of form) fields.set(name, String(value));

		await forgetRunWindow(runFilters(fields));
		return { action: 'refresh' };
	}
};

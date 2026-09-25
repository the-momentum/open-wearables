import {
	fetchConnections,
	purgeConnectionData,
	revokeConnection,
	syncHistory,
	syncNow
} from '$lib/server/connections';
import { attempt } from '$lib/server/form';
import { requireToken } from '$lib/server/guard';
import { fetchProviders } from '$lib/server/providers';
import { fetchRecentRuns, fetchSyncHistory } from '$lib/server/syncs';
import { userActions } from '$lib/server/user-actions';
import { RECENT_WINDOW } from '$lib/syncs/recent';
import type { Actions, PageServerLoad } from './$types';

/** Sync activity is reporting: Redis being down costs the section, not the page. */
async function optional<T>(work: Promise<T>, fallback: T): Promise<T> {
	try {
		return await work;
	} catch {
		return fallback;
	}
}

export const load: PageServerLoad = async ({ params, locals }) => {
	const accessToken = await requireToken(locals);

	// Three sources, three questions: connections say whether live sync works,
	// /sync/history holds backfills for good, /sync/runs the last 24h of
	// everything. Merged, live runs older than a day would silently vanish.
	const [connections, backfills, recentRuns, providers] = await Promise.all([
		fetchConnections(params.id, accessToken),
		optional(fetchSyncHistory(params.id, accessToken), []),
		optional(fetchRecentRuns(params.id, accessToken, RECENT_WINDOW), []),
		fetchProviders(accessToken)
	]);

	return { connections, backfills, recentRuns, providers };
};

const provider = (form: FormData) => String(form.get('provider') ?? '');

export const actions: Actions = {
	...userActions,

	syncNow: async ({ params, request, locals }) => {
		const accessToken = await requireToken(locals);
		const name = provider(await request.formData());

		return attempt('syncNow', { provider: name }, () => syncNow(params.id, name, accessToken));
	},

	syncHistory: async ({ params, request, locals }) => {
		const accessToken = await requireToken(locals);
		const form = await request.formData();
		const name = provider(form);
		const days = Number(form.get('days') ?? 90);

		return attempt('syncHistory', { provider: name }, () =>
			syncHistory(params.id, name, days, accessToken)
		);
	},

	revokeConnection: async ({ params, request, locals }) => {
		const accessToken = await requireToken(locals);
		const name = provider(await request.formData());

		return attempt('revokeConnection', { provider: name }, () =>
			revokeConnection(params.id, name, accessToken)
		);
	},

	purgeConnectionData: async ({ params, request, locals }) => {
		const accessToken = await requireToken(locals);
		const name = provider(await request.formData());

		return attempt('purgeConnectionData', { provider: name }, () =>
			purgeConnectionData(params.id, name, accessToken)
		);
	}
};

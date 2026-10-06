import { requireToken } from '$lib/server/guard';
import { fetchNewestUsers, fetchSystemInfo } from '$lib/server/dashboard';
import { fetchProviders } from '$lib/server/providers';
import type { PageServerLoad } from './$types';

/**
 * Three requests, all cheap, and none of them scoped to a user's data: the
 * figures come from one cached aggregate, the list is an indexed sort, and the
 * provider catalogue is a static list. Nothing here grows with how much data a
 * client has.
 */
export const load: PageServerLoad = async ({ locals }) => {
	const accessToken = await requireToken(locals);

	const [info, users, providers] = await Promise.all([
		fetchSystemInfo(accessToken),
		fetchNewestUsers(accessToken),
		fetchProviders(accessToken)
	]);

	return { info, users: users.items, providers };
};

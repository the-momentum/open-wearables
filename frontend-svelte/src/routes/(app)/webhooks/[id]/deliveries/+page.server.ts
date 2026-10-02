import { error } from '@sveltejs/kit';
import { requireToken } from '$lib/server/guard';
import { listDeliveries, listEventTypes, listSubscriptions } from '$lib/server/webhooks';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params, url, locals }) => {
	const accessToken = await requireToken(locals);

	const limit = 20;
	const status = url.searchParams.get('status') ?? '';
	const eventTypes = url.searchParams.getAll('type').filter(Boolean);

	const [subscriptions, types, deliveries] = await Promise.all([
		listSubscriptions(accessToken),
		listEventTypes(accessToken),
		listDeliveries(params.id, accessToken, {
			limit,
			iterator: url.searchParams.get('iterator') ?? '',
			status,
			eventTypes
		})
	]);

	const subscription = subscriptions.find((entry) => entry.id === params.id);
	if (!subscription) error(404, 'No such webhook subscription');

	return { subscription, types, deliveries, limit, filters: { status, eventTypes } };
};

import { attempt } from '$lib/server/form';
import { requireToken } from '$lib/server/guard';
import {
	createSubscription,
	deleteSubscription,
	listEventTypes,
	listSubscriptions,
	sendTestEvent,
	updateSubscription,
	type SubscriptionInput
} from '$lib/server/webhooks';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals }) => {
	const accessToken = await requireToken(locals);

	const [subscriptions, types] = await Promise.all([
		listSubscriptions(accessToken),
		listEventTypes(accessToken)
	]);

	return { subscriptions, types };
};

/**
 * An empty list of types means "every event" and the API takes it as such, but
 * a blank user id is a different thing from an empty string: null is "every
 * user", and "" would be rejected as a malformed UUID.
 */
function readInput(form: FormData): SubscriptionInput {
	const text = (name: string) => String(form.get(name) ?? '').trim();

	return {
		url: text('url'),
		description: text('description') || null,
		filter_types: form.getAll('filter_types').map(String),
		user_id: text('user_id') || null
	};
}

export const actions: Actions = {
	create: async ({ request, locals }) => {
		const accessToken = await requireToken(locals);
		const input = readInput(await request.formData());

		return attempt('create', input, () => createSubscription(input, accessToken));
	},

	update: async ({ request, locals }) => {
		const accessToken = await requireToken(locals);
		const form = await request.formData();
		const id = String(form.get('id') ?? '');
		const input = readInput(form);

		return attempt('update', { id, ...input }, () => updateSubscription(id, input, accessToken));
	},

	/**
	 * A sample event, sent to one subscription. It lands in that subscription's
	 * own deliveries, which is where the reader already is.
	 */
	test: async ({ request, locals }) => {
		const accessToken = await requireToken(locals);
		const form = await request.formData();
		const id = String(form.get('id') ?? '');
		const eventType = String(form.get('event_type') ?? '');

		return attempt('test', { id, eventType }, () => sendTestEvent(id, eventType, accessToken));
	},

	delete: async ({ request, locals }) => {
		const accessToken = await requireToken(locals);
		const id = String((await request.formData()).get('id') ?? '');

		return attempt('delete', { id }, () => deleteSubscription(id, accessToken));
	}
};

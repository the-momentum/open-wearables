import { attempt, jsonField } from '$lib/server/form';
import { requireToken } from '$lib/server/guard';
import { fetchProviders } from '$lib/server/providers';
import {
	listDeviceTypePriorities,
	listProviderPriorities,
	saveDeviceTypePriorities,
	saveProviderPriorities
} from '$lib/server/settings';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals }) => {
	const accessToken = await requireToken(locals);

	const [providers, deviceTypes, catalogue] = await Promise.all([
		listProviderPriorities(accessToken),
		listDeviceTypePriorities(accessToken),
		fetchProviders(accessToken)
	]);

	return { providers, deviceTypes, catalogue };
};

const ordered = (form: FormData) => jsonField<unknown[]>(form, 'order', []);

export const actions: Actions = {
	saveProviders: async ({ request, locals }) => {
		const accessToken = await requireToken(locals);
		const priorities = ordered(await request.formData());

		return attempt('saveProviders', {}, () => saveProviderPriorities(priorities, accessToken));
	},

	saveDeviceTypes: async ({ request, locals }) => {
		const accessToken = await requireToken(locals);
		const priorities = ordered(await request.formData());

		return attempt('saveDeviceTypes', {}, () => saveDeviceTypePriorities(priorities, accessToken));
	}
};

import { attempt, jsonField } from '$lib/server/form';
import { requireToken } from '$lib/server/guard';
import { forgetProviders } from '$lib/server/providers';
import { listProviderSettings, saveProviderSettings } from '$lib/server/settings';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals }) => {
	const accessToken = await requireToken(locals);

	return { providers: await listProviderSettings(accessToken) };
};

export const actions: Actions = {
	/**
	 * One request for the whole list, not one per switch: the toggles are a draft
	 * until saved, and a provider disabled by accident is a provider nobody can
	 * connect to.
	 */
	save: async ({ request, locals }) => {
		const accessToken = await requireToken(locals);
		const providers = jsonField<Record<string, boolean>>(await request.formData(), 'providers', {});

		return attempt('save', {}, async () => {
			await saveProviderSettings(providers, accessToken);
			forgetProviders();
		});
	}
};

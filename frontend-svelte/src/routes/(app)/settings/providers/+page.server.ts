import { attempt, field, jsonField } from '$lib/server/form';
import { requireToken } from '$lib/server/guard';
import { listProviderSettings, saveProviderSettings, setLiveSyncMode } from '$lib/server/settings';
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

		return attempt('save', {}, () => saveProviderSettings(providers, accessToken));
	},

	/** How one provider reports new data — its own setting, saved on the click. */
	liveSync: async ({ request, locals }) => {
		const accessToken = await requireToken(locals);
		const form = await request.formData();
		const provider = field(form, 'provider');
		const mode = field(form, 'mode');

		return attempt('liveSync', { provider }, () => setLiveSyncMode(provider, mode, accessToken));
	}
};

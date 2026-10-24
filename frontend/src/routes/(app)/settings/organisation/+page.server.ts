import { attempt, field } from '$lib/server/form';
import { requireToken } from '$lib/server/guard';
import { fetchInstanceSettings, saveInstanceSettings } from '$lib/server/instance';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals }) => {
	const accessToken = await requireToken(locals);
	return { settings: await fetchInstanceSettings(accessToken) };
};

export const actions: Actions = {
	save: async ({ request, locals }) => {
		const accessToken = await requireToken(locals);
		const form = await request.formData();
		const update = {
			organization_name: field(form, 'organization_name') || null,
			logo_url: field(form, 'logo_url') || null,
			support_email: field(form, 'support_email') || null
		};

		return attempt(
			'save',
			update,
			() => saveInstanceSettings(update, accessToken),
			() => ({
				saved: true
			})
		);
	}
};

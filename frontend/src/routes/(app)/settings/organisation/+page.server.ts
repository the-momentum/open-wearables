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
	},

	saveLegal: async ({ request, locals }) => {
		const accessToken = await requireToken(locals);
		const form = await request.formData();
		const update = {
			privacy_policy_url: field(form, 'privacy_policy_url') || null,
			terms_url: field(form, 'terms_url') || null,
			require_acceptance: field(form, 'require_acceptance') === 'true'
		};

		return attempt(
			'saveLegal',
			update,
			() => saveInstanceSettings(update, accessToken),
			() => ({ saved: true })
		);
	},

	publishLegal: async ({ locals }) => {
		const accessToken = await requireToken(locals);
		return attempt(
			'publishLegal',
			{},
			() => saveInstanceSettings({ bump_legal_documents_version: true }, accessToken),
			() => ({ saved: true })
		);
	}
};

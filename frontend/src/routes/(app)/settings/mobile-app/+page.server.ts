import { attempt, field } from '$lib/server/form';
import { requireToken } from '$lib/server/guard';
import {
	fetchAppEntitlement,
	fetchAppRegistration,
	registerApp,
	unregisterApp,
	type AppEntitlement
} from '$lib/server/app-registration';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals, parent }) => {
	const accessToken = await requireToken(locals);
	const [{ developer }, registration] = await Promise.all([
		parent(),
		fetchAppRegistration(accessToken)
	]);
	let entitlement: AppEntitlement | null = null;
	if (registration.status === 'active') {
		// The license server being down must not take the tab with it.
		entitlement = await fetchAppEntitlement(accessToken).catch(() => null);
	}
	return { registration, entitlement, developerEmail: developer?.email ?? '' };
};

export const actions: Actions = {
	register: async ({ request, locals }) => {
		const accessToken = await requireToken(locals);
		const form = await request.formData();
		const input = {
			admin_email: field(form, 'admin_email'),
			accept_terms: form.get('accept_terms') === 'on',
			marketing_consent: form.get('marketing_consent') === 'on'
		};
		return attempt('register', input, () => registerApp(input, accessToken));
	},

	unregister: async ({ locals }) => {
		const accessToken = await requireToken(locals);
		return attempt('unregister', {}, () => unregisterApp(accessToken));
	}
};

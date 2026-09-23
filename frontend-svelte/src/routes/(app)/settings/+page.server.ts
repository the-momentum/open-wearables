import { attempt, field } from '$lib/server/form';
import { requireToken } from '$lib/server/guard';
import {
	createApiKey,
	createApplication,
	deleteApiKey,
	deleteApplication,
	listApiKeys,
	listApplications,
	renameApiKey,
	rotateApiKey,
	rotateApplicationSecret
} from '$lib/server/settings';
import type { ApiKeySecret, ApplicationSecret } from '$lib/settings/types';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals }) => {
	const accessToken = await requireToken(locals);

	const [keys, applications] = await Promise.all([
		listApiKeys(accessToken),
		listApplications(accessToken)
	]);

	return { keys, applications };
};

/**
 * The secret travels back in the action result and nowhere else: the API hashes
 * it on the way in, so a reload of this page can never show it again.
 */
const keySecret = (title: string) => (key: ApiKeySecret) => ({
	secret: { title, fields: [{ label: key.name, value: key.key }] }
});

const appSecret = (title: string) => (app: ApplicationSecret) => ({
	secret: {
		title,
		fields: [
			{ label: 'App ID', value: app.app_id },
			{ label: 'App secret', value: app.app_secret }
		]
	}
});

export const actions: Actions = {
	createKey: async ({ request, locals }) => {
		const accessToken = await requireToken(locals);
		const name = field(await request.formData(), 'name');

		return attempt(
			'createKey',
			{ name },
			() => createApiKey(name, accessToken),
			keySecret('API key created')
		);
	},

	renameKey: async ({ request, locals }) => {
		const accessToken = await requireToken(locals);
		const form = await request.formData();
		const id = field(form, 'id');
		const name = field(form, 'name');

		return attempt('renameKey', { id, name }, () => renameApiKey(id, name, accessToken));
	},

	rotateKey: async ({ request, locals }) => {
		const accessToken = await requireToken(locals);
		const id = field(await request.formData(), 'id');

		return attempt(
			'rotateKey',
			{ id },
			() => rotateApiKey(id, accessToken),
			keySecret('API key rotated')
		);
	},

	deleteKey: async ({ request, locals }) => {
		const accessToken = await requireToken(locals);
		const id = field(await request.formData(), 'id');

		return attempt('deleteKey', { id }, () => deleteApiKey(id, accessToken));
	},

	createApp: async ({ request, locals }) => {
		const accessToken = await requireToken(locals);
		const name = field(await request.formData(), 'name');

		return attempt(
			'createApp',
			{ name },
			() => createApplication(name, accessToken),
			appSecret('Application created')
		);
	},

	rotateApp: async ({ request, locals }) => {
		const accessToken = await requireToken(locals);
		const appId = field(await request.formData(), 'appId');

		return attempt(
			'rotateApp',
			{ appId },
			() => rotateApplicationSecret(appId, accessToken),
			appSecret('App secret rotated')
		);
	},

	deleteApp: async ({ request, locals }) => {
		const accessToken = await requireToken(locals);
		const appId = field(await request.formData(), 'appId');

		return attempt('deleteApp', { appId }, () => deleteApplication(appId, accessToken));
	}
};

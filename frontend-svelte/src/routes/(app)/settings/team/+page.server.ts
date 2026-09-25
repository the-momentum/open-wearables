import { fail } from '@sveltejs/kit';
import { attempt, describe, field } from '$lib/server/form';
import { requireToken } from '$lib/server/guard';
import { newPasswordProblem } from '$lib/settings/password';
import {
	changePassword,
	createInvitation,
	listDevelopers,
	listInvitations,
	removeDeveloper,
	resendInvitation,
	revokeInvitation
} from '$lib/server/settings';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals }) => {
	const accessToken = await requireToken(locals);

	const [developers, invitations] = await Promise.all([
		listDevelopers(accessToken),
		listInvitations(accessToken)
	]);

	return { developers, invitations };
};

export const actions: Actions = {
	invite: async ({ request, locals }) => {
		const accessToken = await requireToken(locals);
		const email = field(await request.formData(), 'email');

		return attempt('invite', { email }, () => createInvitation(email, accessToken));
	},

	resendInvite: async ({ request, locals }) => {
		const accessToken = await requireToken(locals);
		const id = field(await request.formData(), 'id');

		return attempt('resendInvite', { id }, () => resendInvitation(id, accessToken));
	},

	revokeInvite: async ({ request, locals }) => {
		const accessToken = await requireToken(locals);
		const id = field(await request.formData(), 'id');

		return attempt('revokeInvite', { id }, () => revokeInvitation(id, accessToken));
	},

	/**
	 * Your own password, not anyone else's: the API changes the password of
	 * whoever the token belongs to, which is why this lives on your own row.
	 */
	changePassword: async ({ request, locals }) => {
		const accessToken = await requireToken(locals);
		const form = await request.formData();

		const body = {
			current_password: String(form.get('current_password') ?? ''),
			new_password: String(form.get('new_password') ?? ''),
			confirm_password: String(form.get('confirm_password') ?? '')
		};

		const action = 'changePassword';
		const problem = newPasswordProblem(body.new_password, body.confirm_password);
		if (problem) return fail(400, { action, message: problem });

		try {
			await changePassword(body, accessToken);
		} catch (error) {
			return fail(400, { action, message: describe(error) });
		}

		return { action };
	},

	removeMember: async ({ request, locals }) => {
		const accessToken = await requireToken(locals);
		const id = field(await request.formData(), 'id');

		return attempt('removeMember', { id }, () => removeDeveloper(id, accessToken));
	}
};

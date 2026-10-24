import { fail, redirect } from '@sveltejs/kit';
import type { Actions } from '@sveltejs/kit';
import { resolve } from '$app/paths';
import { attempt, describe, field } from './form';
import { requireToken } from './guard';
import { appSeats, fetchAppRegistration } from './app-registration';
import { emailInvitationCode, generateInvitationCode } from './invitations';
import { deleteUser, readUserInput, updateUser } from './users';

/** Shared by every tab: a form action resolves against the route showing. */
export const userActions: Actions = {
	update: async ({ params, request, locals }) => {
		const accessToken = await requireToken(locals);
		const input = readUserInput(await request.formData());

		return attempt('update', { id: params.id, ...input }, () =>
			updateUser(params.id!, input, accessToken)
		);
	},

	invite: async ({ params, locals }) => {
		const accessToken = await requireToken(locals);

		try {
			const [invitation, registration, seats] = await Promise.all([
				generateInvitationCode(params.id!, accessToken),
				fetchAppRegistration(accessToken).catch(() => null),
				appSeats(accessToken)
			]);
			return { action: 'invite', invitation, appEnabled: registration?.status === 'active', seats };
		} catch (error) {
			return fail(400, { action: 'invite', message: describe(error) });
		}
	},

	emailInvite: async ({ params, request, locals }) => {
		const accessToken = await requireToken(locals);
		const email = field(await request.formData(), 'email');
		return attempt(
			'emailInvite',
			{ email },
			() => emailInvitationCode(params.id!, email, accessToken),
			(sent) => ({
				sentTo: sent.sent_to
			})
		);
	},

	delete: async ({ params, locals }) => {
		const accessToken = await requireToken(locals);

		// Not attempt(): it would catch the redirect and report success as failure.
		try {
			await deleteUser(params.id!, accessToken);
		} catch (error) {
			return fail(400, { action: 'delete', id: params.id, message: describe(error) });
		}
		redirect(303, resolve('/users'));
	}
};

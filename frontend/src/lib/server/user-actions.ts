import { fail, redirect } from '@sveltejs/kit';
import type { Actions } from '@sveltejs/kit';
import { resolve } from '$app/paths';
import { attempt, describe } from './form';
import { requireToken } from './guard';
import { generateInvitationCode } from './invitations';
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
			const invitation = await generateInvitationCode(params.id!, accessToken);
			return { action: 'invite', invitation };
		} catch (error) {
			return fail(400, { action: 'invite', message: describe(error) });
		}
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

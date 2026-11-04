import { fail, redirect } from '@sveltejs/kit';
import { resolve } from '$app/paths';
import { describe } from '$lib/server/form';
import { requireToken } from '$lib/server/guard';
import { clearPasswordChange } from '$lib/server/session';
import { changePassword } from '$lib/server/settings';
import { newPasswordProblem } from '$lib/settings/password';
import type { Actions, PageServerLoad } from './$types';

// Reached only from sign-in with the public default password, which the
// (app) layout keeps sending back here until it changes.

export const load: PageServerLoad = async ({ locals }) => {
	await requireToken(locals);
	const session = locals.auth.session();
	if (!session?.passwordChange) redirect(303, resolve('/dashboard'));

	return {
		email: session.developer.email,
		required: session.passwordChange === 'required'
	};
};

export const actions: Actions = {
	change: async ({ request, locals, cookies }) => {
		const accessToken = await requireToken(locals);
		const form = await request.formData();

		const body = {
			current_password: String(form.get('current_password') ?? ''),
			new_password: String(form.get('new_password') ?? ''),
			confirm_password: String(form.get('confirm_password') ?? '')
		};

		const problem = newPasswordProblem(body.new_password, body.confirm_password);
		if (problem) return fail(400, { message: problem });

		try {
			await changePassword(body, accessToken);
		} catch (error) {
			return fail(400, { message: describe(error) });
		}

		clearPasswordChange(cookies);
		redirect(303, resolve('/dashboard'));
	},

	/** Outside production only: a local stack can keep the default. */
	skip: async ({ locals, cookies }) => {
		if (locals.auth.session()?.passwordChange !== 'recommended') {
			return fail(403, { message: 'Change the password to continue.' });
		}
		clearPasswordChange(cookies);
		redirect(303, resolve('/dashboard'));
	}
};

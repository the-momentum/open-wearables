import { fail, redirect } from '@sveltejs/kit';
import { resolve } from '$app/paths';
import { API, ApiError, apiGet, login, type Developer } from '$lib/server/api';
import { field } from '$lib/server/form';
import { createSession } from '$lib/server/session';
import { acceptInvitation } from '$lib/server/settings';
import { newPasswordProblem } from '$lib/settings/password';
import type { Actions, PageServerLoad } from './$types';

// The backend writes this path and `token` into every invitation email.

export const load: PageServerLoad = async ({ url, locals }) => {
	if (locals.auth.session()) redirect(303, resolve('/dashboard'));
	return { token: url.searchParams.get('token') ?? '' };
};

const DEAD_LINKS: Record<string, string> = {
	INVITATION_EXPIRED: 'This invitation has expired',
	INVITATION_ALREADY_ACCEPTED: 'This invitation has already been used',
	INVITATION_WITHDRAWN: 'This invitation was withdrawn'
};

function deadLink(error: ApiError): string | null {
	if (error.status === 404) return 'This invitation link is not valid';
	return (error.code && DEAD_LINKS[error.code]) || null;
}

export const actions: Actions = {
	default: async ({ request, url, cookies }) => {
		const form = await request.formData();
		const token = url.searchParams.get('token') ?? '';
		const first = field(form, 'first_name');
		const last = field(form, 'last_name');
		const password = String(form.get('password') ?? '');
		const kept = { first, last };

		if (!token) return fail(400, { ...kept, dead: 'This invitation link is not valid' });
		if (!first || !last) return fail(400, { ...kept, message: 'Enter your first and last name.' });
		const problem = newPasswordProblem(password, String(form.get('confirm_password') ?? ''));
		if (problem) return fail(400, { ...kept, message: problem });

		let developer: Developer;
		try {
			developer = await acceptInvitation({
				token,
				first_name: first,
				last_name: last,
				password
			});
		} catch (error) {
			const dead = error instanceof ApiError ? deadLink(error) : null;
			if (dead) return fail(400, { ...kept, dead });
			return fail(503, {
				...kept,
				message: 'Your account could not be created. Try again in a moment.'
			});
		}

		// Signed straight in; if that fails the account still exists, so point to sign-in.
		try {
			const tokens = await login(developer.email, password);
			createSession(cookies, tokens, await apiGet<Developer>(API.me, tokens.access_token));
		} catch {
			return { joined: developer.email };
		}

		redirect(303, resolve('/dashboard'));
	}
};

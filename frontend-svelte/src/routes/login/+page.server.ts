import { fail, redirect } from '@sveltejs/kit';
import { resolve } from '$app/paths';
import { API, ApiError, apiGet, login, type Developer } from '$lib/server/api';
import { createSession, readSession } from '$lib/server/session';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ cookies }) => {
	if (await readSession(cookies)) redirect(303, resolve('/dashboard'));
};

export const actions: Actions = {
	default: async ({ request, cookies }) => {
		const form = await request.formData();
		const email = String(form.get('email') ?? '').trim();
		const password = String(form.get('password') ?? '');

		if (!email || !password) {
			return fail(400, { email, message: 'Enter your email and password.' });
		}

		try {
			const tokens = await login(email, password);
			const developer = await apiGet<Developer>(API.me, tokens.access_token);
			await createSession(cookies, tokens, developer);
		} catch (error) {
			// One message for both: naming the wrong field reveals which accounts exist.
			if (error instanceof ApiError && error.status === 401) {
				return fail(401, { email, message: 'Incorrect email or password.' });
			}
			return fail(503, { email, message: 'Could not reach the server. Try again.' });
		}

		// Outside the try: redirect() throws, and would be caught above.
		redirect(303, resolve('/dashboard'));
	}
};

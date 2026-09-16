import { redirect } from '@sveltejs/kit';
import { resolve } from '$app/paths';
import { destroySession } from '$lib/server/session';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = () => {
	redirect(303, resolve('/login'));
};

export const actions: Actions = {
	default: async ({ cookies }) => {
		await destroySession(cookies);
		redirect(303, resolve('/login'));
	}
};

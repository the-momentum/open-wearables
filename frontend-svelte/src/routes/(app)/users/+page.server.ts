import { fail, redirect } from '@sveltejs/kit';
import { attempt } from '$lib/server/form';
import { requireToken } from '$lib/server/guard';
import { fetchProviders } from '$lib/server/providers';
import { createUser, deleteUser, fetchUsers, readUserInput, updateUser } from '$lib/server/users';
import { parseUsersQuery, usersQueryHref, withUsersQuery } from '$lib/users/query';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ url, locals }) => {
	const accessToken = await requireToken(locals);

	const query = parseUsersQuery(url.searchParams);
	const [users, providers] = await Promise.all([
		fetchUsers(query, accessToken),
		fetchProviders(accessToken)
	]);

	// A stale deep link, or a page-size change made against a total that has
	// since shrunk, would otherwise render a dead empty page.
	if (users.total > 0 && query.page > users.pages) {
		redirect(303, usersQueryHref(withUsersQuery(query, { page: users.pages })));
	}

	return { query, users, providers };
};

export const actions: Actions = {
	create: async ({ request, locals }) => {
		const accessToken = await requireToken(locals);
		const input = readUserInput(await request.formData());

		if (!input.first_name && !input.last_name && !input.email) {
			return fail(400, { action: 'create', ...input, message: 'Enter a name or an email.' });
		}
		return attempt('create', input, () => createUser(input, accessToken));
	},

	update: async ({ request, locals }) => {
		const accessToken = await requireToken(locals);
		const form = await request.formData();
		const id = String(form.get('id') ?? '');
		const input = readUserInput(form);

		return attempt('update', { id, ...input }, () => updateUser(id, input, accessToken));
	},

	delete: async ({ request, locals }) => {
		const accessToken = await requireToken(locals);
		const id = String((await request.formData()).get('id') ?? '');

		return attempt('delete', { id }, () => deleteUser(id, accessToken));
	}
};

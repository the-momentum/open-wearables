import { fail, redirect } from '@sveltejs/kit';
import { resolve } from '$app/paths';
import { attempt } from '$lib/server/form';
import { requireToken } from '$lib/server/guard';
import {
	cachedLifecycle,
	fetchLifecycle,
	runLifecycle,
	saveLifecycle
} from '$lib/server/lifecycle';
import { fromFields, invalid, settingsOf } from '$lib/lifecycle/projection';
import type { Actions, PageServerLoad } from './$types';

/** A hit is handed over as it is; a miss is streamed, so the tab opens on a skeleton. */
export const load: PageServerLoad = async ({ locals, parent }) => {
	if (!(await parent()).features.lifecycle) redirect(303, resolve('/settings'));
	const accessToken = await requireToken(locals);

	return { lifecycle: cachedLifecycle() ?? fetchLifecycle(accessToken) };
};

export const actions: Actions = {
	save: async ({ request, locals }) => {
		const accessToken = await requireToken(locals);
		const policy = fromFields(await request.formData());

		// Checked again here: the form refuses these, but it is only the browser.
		const problem = invalid(policy);
		if (problem) return fail(400, { action: 'save', message: problem });

		return attempt('save', {}, () => saveLifecycle(settingsOf(policy), accessToken));
	},

	run: async ({ locals }) => {
		const accessToken = await requireToken(locals);

		return attempt(
			'run',
			{},
			() => runLifecycle(accessToken),
			() => ({ dispatched: true })
		);
	}
};

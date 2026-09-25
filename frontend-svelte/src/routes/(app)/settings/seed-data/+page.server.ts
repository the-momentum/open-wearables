import { fail } from '@sveltejs/kit';
import { attempt, jsonField } from '$lib/server/form';
import { requireToken } from '$lib/server/guard';
import { fetchCoverage } from '$lib/server/coverage';
import { generateSeed, listPresets, listSleepProfiles } from '$lib/server/seed';
import { listProviderSettings } from '$lib/server/settings';
import { SEED_PROVIDERS, seriesGroups } from '$lib/seed/catalogue';
import { problems, requestOf, type Draft } from '$lib/seed/draft';
import type { Actions, PageServerLoad } from './$types';

/** Four static reads; the coverage matrix only to group the series, so it stays here. */
export const load: PageServerLoad = async ({ locals }) => {
	const accessToken = await requireToken(locals);

	const [presets, sleepProfiles, coverage, providers] = await Promise.all([
		listPresets(accessToken),
		listSleepProfiles(accessToken),
		fetchCoverage(accessToken),
		listProviderSettings(accessToken)
	]);

	return {
		presets,
		sleepProfiles,
		series: seriesGroups(presets, coverage),
		// Every one, enabled or not: seeding a disabled provider is a fair test.
		providers: SEED_PROVIDERS.map(
			(slug) =>
				providers.find((provider) => provider.provider === slug) ?? {
					provider: slug,
					name: slug,
					icon_url: ''
				}
		)
	};
};

export const actions: Actions = {
	generate: async ({ request, locals }) => {
		const accessToken = await requireToken(locals);
		const posted = jsonField<{ draft: Draft; preset: string | null } | null>(
			await request.formData(),
			'seed',
			null
		);

		if (!posted)
			return fail(400, { action: 'generate', message: 'The form did not arrive whole.' });

		// Checked again here: the form refuses these, but it is only the browser.
		const found = problems(posted.draft);
		if (found.length > 0) return fail(400, { action: 'generate', message: found[0] });

		return attempt(
			'generate',
			{},
			() => generateSeed(requestOf(posted.draft, posted.preset), accessToken),
			(result) => ({ seed: result.seed_used, task: result.task_id, users: posted.draft.users })
		);
	}
};

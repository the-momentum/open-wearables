import { fetchConnections } from '$lib/server/connections';
import { requireToken } from '$lib/server/guard';
import { knownProvider } from '$lib/server/events';
import { fetchProviders } from '$lib/server/providers';
import { deleteWorkout, fetchWorkoutTypes, fetchWorkouts } from '$lib/server/workouts';
import { attempt } from '$lib/server/form';
import { userActions } from '$lib/server/user-actions';
import { parsePeriod } from '$lib/filters/period';
import { isPageSize } from '$lib/lists/pagination';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params, url, locals }) => {
	const accessToken = await requireToken(locals);
	const period = parsePeriod(url.searchParams);

	const askedProvider = url.searchParams.get('provider') ?? '';
	const askedType = url.searchParams.get('type') ?? '';
	const cursor = url.searchParams.get('cursor') ?? '';

	// Ten, not the list default of twenty: these cards expand, and twenty of them
	// is a page nobody reaches the end of. The sizes on offer are the shared ones.
	const asked = Number(url.searchParams.get('size'));
	const pageSize = isPageSize(asked) ? asked : 10;

	// Both option lists span the user's whole history, not the chosen period, so
	// neither control empties itself as you step through days. A provider or a
	// type with nothing this week is exactly what an admin wants to select.
	const options = Promise.all([
		fetchProviders(accessToken),
		fetchConnections(params.id, accessToken),
		fetchWorkoutTypes(params.id, accessToken)
	]);

	const query = (provider: string, type: string) =>
		fetchWorkouts(params.id, accessToken, { period, provider, type, cursor, limit: pageSize });

	// With neither filter asked for there is nothing to check, so the list query
	// travels alongside the option lists instead of queueing behind them.
	const started = !askedProvider && !askedType ? query('', '') : null;

	const [providers, connections, everyType] = await options;
	const types = [...everyType].sort();

	const provider = knownProvider(connections, askedProvider);
	// The same rule for the type: `WorkoutType` is an enum too.
	const type = types.includes(askedType) ? askedType : '';

	const workouts = (await started) ?? (await query(provider, type));

	return {
		period,
		provider,
		type,
		types,
		workouts,
		providers,
		connections,
		pageSize
	};
};

export const actions: Actions = {
	// The header sits in the layout, so its actions have to exist on every tab.
	...userActions,

	deleteWorkout: async ({ params, request, locals }) => {
		const accessToken = await requireToken(locals);
		const id = String((await request.formData()).get('workout') ?? '');

		return attempt('deleteWorkout', { workout: id }, () =>
			deleteWorkout(params.id, id, accessToken)
		);
	}
};

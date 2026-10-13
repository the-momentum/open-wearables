import { apiDelete, apiGet } from './api';
import { eventWindow, periodBounds } from './events';
import type { Period } from '$lib/filters/period';
import type { WorkoutPage, WorkoutTotalsResponse } from '$lib/workouts/types';

export type WorkoutQuery = {
	period: Period;
	provider?: string;
	/** Drops a workout a higher-priority source already recorded, by the ranking summaries use. */
	topSourceOnly?: boolean;
	type?: string;
	cursor?: string;
	limit?: number;
};

/** The filters the list and its totals share, so both count the same workouts. */
function filterParams(
	params: URLSearchParams,
	{
		provider,
		type,
		topSourceOnly
	}: Pick<Required<WorkoutQuery>, 'provider' | 'type' | 'topSourceOnly'>
) {
	if (provider) params.set('provider', provider);
	if (type) params.set('type', type);
	if (topSourceOnly) params.set('filter_by_priority', 'true');
	return params;
}

export function fetchWorkouts(
	userId: string,
	accessToken: string,
	{ period, provider = '', type = '', topSourceOnly = false, cursor = '', limit = 10 }: WorkoutQuery
): Promise<WorkoutPage> {
	const params = filterParams(eventWindow(period, limit), { provider, type, topSourceOnly });
	// A card cannot draw zones until it is expanded, but paging again on expand
	// would be worse than carrying them.
	params.set('include', 'zones');
	if (cursor) params.set('cursor', cursor);

	return apiGet<WorkoutPage>(`/api/v1/users/${userId}/events/workouts?${params}`, accessToken);
}

/** Every matching workout in the period, added up by the API rather than paged through. */
export function fetchWorkoutTotals(
	userId: string,
	accessToken: string,
	{
		period,
		provider = '',
		type = '',
		topSourceOnly = false
	}: Pick<WorkoutQuery, 'period' | 'provider' | 'type' | 'topSourceOnly'>
): Promise<WorkoutTotalsResponse> {
	return apiGet<WorkoutTotalsResponse>(
		`/api/v1/users/${userId}/events/workouts/totals?${filterParams(periodBounds(period), { provider, type, topSourceOnly })}`,
		accessToken
	);
}

export const deleteWorkout = (userId: string, workoutId: string, accessToken: string) =>
	apiDelete(`/api/v1/users/${userId}/events/workouts/${workoutId}`, accessToken);

/** The types this user actually has, so the filter offers nothing that is empty. */
export const fetchWorkoutTypes = (userId: string, accessToken: string) =>
	apiGet<string[]>(`/api/v1/users/${userId}/events/workouts/types`, accessToken);

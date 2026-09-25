import { apiDelete, apiGet } from './api';
import { eventWindow } from './events';
import type { Period } from '$lib/filters/period';
import type { WorkoutPage } from '$lib/workouts/types';

export type WorkoutQuery = {
	period: Period;
	provider?: string;
	type?: string;
	cursor?: string;
	limit?: number;
	/** Zones are a second table read, so the totals pass asks for none. */
	zones?: boolean;
};

export function fetchWorkouts(
	userId: string,
	accessToken: string,
	{ period, provider = '', type = '', cursor = '', limit = 10, zones = true }: WorkoutQuery
): Promise<WorkoutPage> {
	const params = eventWindow(period, limit);
	// A card cannot draw zones until it is expanded, but paging again on expand
	// would be worse than carrying them.
	if (zones) params.set('include', 'zones');
	if (provider) params.set('provider', provider);
	if (type) params.set('type', type);
	if (cursor) params.set('cursor', cursor);

	return apiGet<WorkoutPage>(`/api/v1/users/${userId}/events/workouts?${params}`, accessToken);
}

export const deleteWorkout = (userId: string, workoutId: string, accessToken: string) =>
	apiDelete(`/api/v1/users/${userId}/events/workouts/${workoutId}`, accessToken);

/** The types this user actually has, so the filter offers nothing that is empty. */
export const fetchWorkoutTypes = (userId: string, accessToken: string) =>
	apiGet<string[]>(`/api/v1/users/${userId}/events/workouts/types`, accessToken);

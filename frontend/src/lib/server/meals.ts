import { apiDelete, apiGet } from './api';
import { eventWindow } from './events';
import type { Period } from '$lib/filters/period';
import type { MealPage } from '$lib/meals/types';

export type MealQuery = { period: Period; provider?: string; cursor?: string; limit?: number };

export function fetchMeals(
	userId: string,
	accessToken: string,
	{ period, provider = '', cursor = '', limit = 10 }: MealQuery
): Promise<MealPage> {
	const params = eventWindow(period, limit);
	if (provider) params.set('provider', provider);
	if (cursor) params.set('cursor', cursor);

	return apiGet<MealPage>(`/api/v1/users/${userId}/events/meals?${params}`, accessToken);
}

export const deleteMeal = (userId: string, mealId: string, accessToken: string) =>
	apiDelete(`/api/v1/users/${userId}/events/meals/${mealId}`, accessToken);

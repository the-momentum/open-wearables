import { apiDelete, apiGet } from './api';
import { eventWindow } from './events';
import type { Period } from '$lib/filters/period';
import type { SleepPage } from '$lib/sleep/types';

export type SleepQuery = {
	period: Period;
	provider?: string;
	/** Keeps only the winning source per night, the same ranking summaries use. */
	topSourceOnly?: boolean;
	cursor?: string;
	limit?: number;
	/** Stage intervals are a second table read, so the totals pass asks for none. */
	stages?: boolean;
};

export function fetchSleep(
	userId: string,
	accessToken: string,
	{
		period,
		provider = '',
		topSourceOnly = false,
		cursor = '',
		limit = 10,
		stages = true
	}: SleepQuery
): Promise<SleepPage> {
	const params = eventWindow(period, limit);
	// A card cannot draw a hypnogram until it is expanded, but paging again on
	// expand would be worse than carrying the intervals.
	if (stages) params.set('include', 'stages');
	if (provider) params.set('provider', provider);
	if (topSourceOnly) params.set('filter_by_priority', 'true');
	if (cursor) params.set('cursor', cursor);

	return apiGet<SleepPage>(`/api/v1/users/${userId}/events/sleep?${params}`, accessToken);
}

export const deleteSleep = (userId: string, sleepId: string, accessToken: string) =>
	apiDelete(`/api/v1/users/${userId}/events/sleep/${sleepId}`, accessToken);

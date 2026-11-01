import { apiDelete, apiGet } from './api';
import { eventWindow, periodBounds } from './events';
import type { Period } from '$lib/filters/period';
import { isNapParam, type SessionFilter } from '$lib/sleep/query';
import type { SleepPage, SleepTotalsResponse } from '$lib/sleep/types';

export type SleepQuery = {
	period: Period;
	provider?: string;
	/** Keeps only the winning source per night, the same ranking summaries use. */
	topSourceOnly?: boolean;
	kind?: SessionFilter;
	cursor?: string;
	limit?: number;
};

/** The filters the list and its totals share, so both count the same sessions. */
function filterParams(
	params: URLSearchParams,
	{
		provider,
		topSourceOnly,
		kind
	}: Pick<Required<SleepQuery>, 'provider' | 'topSourceOnly' | 'kind'>
) {
	if (provider) params.set('provider', provider);
	if (topSourceOnly) params.set('filter_by_priority', 'true');
	const nap = isNapParam(kind);
	if (nap) params.set('is_nap', nap);
	return params;
}

export function fetchSleep(
	userId: string,
	accessToken: string,
	{
		period,
		provider = '',
		topSourceOnly = false,
		kind = 'all',
		cursor = '',
		limit = 10
	}: SleepQuery
): Promise<SleepPage> {
	const params = filterParams(eventWindow(period, limit), { provider, topSourceOnly, kind });
	// A card cannot draw a hypnogram until it is expanded, but paging again on
	// expand would be worse than carrying the intervals.
	params.set('include', 'stages');
	if (cursor) params.set('cursor', cursor);

	return apiGet<SleepPage>(`/api/v1/users/${userId}/events/sleep?${params}`, accessToken);
}

/** Every matching session in the period, added up by the API rather than paged through. */
export function fetchSleepTotals(
	userId: string,
	accessToken: string,
	{
		period,
		provider = '',
		topSourceOnly = false,
		kind = 'all'
	}: Omit<SleepQuery, 'cursor' | 'limit'>
): Promise<SleepTotalsResponse> {
	const params = periodBounds(period);
	return apiGet<SleepTotalsResponse>(
		`/api/v1/users/${userId}/events/sleep/totals?${filterParams(params, { provider, topSourceOnly, kind })}`,
		accessToken
	);
}

export const deleteSleep = (userId: string, sleepId: string, accessToken: string) =>
	apiDelete(`/api/v1/users/${userId}/events/sleep/${sleepId}`, accessToken);

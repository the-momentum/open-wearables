import { apiDelete, apiGet } from './api';
import { eventWindow } from './events';
import { ALL_TIME } from '$lib/filters/period';
import type { CyclePage } from '$lib/cycles/types';

/**
 * Always the whole history: this endpoint drops the upper bound of the window
 * on purpose — a cycle running now ends in the future, and filtering on
 * `end_datetime` would hide exactly the cycle a reader came for. A period
 * control would therefore narrow one end of the range and not the other.
 */
export function fetchCycles(
	userId: string,
	accessToken: string,
	{ cursor = '', limit = 10 }: { cursor?: string; limit?: number } = {}
): Promise<CyclePage> {
	const params = eventWindow(ALL_TIME, limit);
	if (cursor) params.set('cursor', cursor);

	return apiGet<CyclePage>(
		`/api/v1/users/${userId}/events/menstrual-cycles?${params}`,
		accessToken
	);
}

export const deleteCycle = (userId: string, cycleId: string, accessToken: string) =>
	apiDelete(`/api/v1/users/${userId}/events/menstrual-cycles/${cycleId}`, accessToken);

import { apiGet } from './api';
import { eventWindow } from './events';
import type { ActivityPage } from '$lib/activity/types';
import type { Period } from '$lib/filters/period';

export type ActivityQuery = { period: Period; cursor?: string; limit?: number };

/**
 * Newest first, unlike the endpoint's own default: every other list on this site
 * reads that way, and an admin opening a tab wants the last few days.
 *
 * There is no provider parameter because there is nothing to filter — the
 * service keeps the highest-priority source per date before it answers.
 */
export function fetchActivity(
	userId: string,
	accessToken: string,
	{ period, cursor = '', limit = 10 }: ActivityQuery
): Promise<ActivityPage> {
	const params = eventWindow(period, limit);
	params.set('sort_order', 'desc');
	if (cursor) params.set('cursor', cursor);

	return apiGet<ActivityPage>(`/api/v1/users/${userId}/summaries/activity?${params}`, accessToken);
}

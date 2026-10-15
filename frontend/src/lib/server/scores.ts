import { apiGet } from './api';
import { eventWindow, SUMMARY_CAP, tomorrow, windowParams } from './events';
import { DAY_MS, periodWindow, type Period } from '$lib/filters/period';
import type { DayWindow } from '$lib/scores/paging';
import type { ScorePage } from '$lib/scores/types';
import { localDayKey } from '$lib/utils/format';

const path = (userId: string) => `/api/v1/users/${userId}/health-scores`;

/**
 * The days a page can be cut from. A chosen period says so itself; "All time"
 * has to be found out, because paging by day needs a first day to count back
 * from and this endpoint only ever answers newest-first.
 *
 * Two small requests, and only for "All time": the count rides along with any
 * response, and the oldest record is the one at the end of it.
 */
export async function scoreDays(
	userId: string,
	accessToken: string,
	period: Period
): Promise<DayWindow> {
	const chosen = periodWindow(period);
	if (chosen) return chosen;

	const to = tomorrow();
	// One empty day, so the bar has a page to be on and nothing divides by zero.
	const nothing = { from: new Date(to.getTime() - DAY_MS), to };

	const counted = await apiGet<ScorePage>(`${path(userId)}?limit=1`, accessToken);
	const total = counted.pagination.total_count;
	if (total < 1) return nothing;

	const tail = await apiGet<ScorePage>(`${path(userId)}?limit=1&offset=${total - 1}`, accessToken);
	const oldest = tail.data[0];
	if (!oldest) return nothing;

	return {
		from: new Date(`${localDayKey(oldest.recorded_at, oldest.zone_offset)}T00:00:00Z`),
		to
	};
}

/**
 * One page's worth of days. `SUMMARY_CAP` rather than a page size, because how
 * many records sit behind a day is the provider's business.
 */
export function fetchScoreDays(
	userId: string,
	accessToken: string,
	window: DayWindow,
	category: string
): Promise<ScorePage> {
	const params = windowParams(window.from, window.to, SUMMARY_CAP);
	if (category) params.set('category', category);

	return apiGet<ScorePage>(`${path(userId)}?${params}`, accessToken);
}

/**
 * Every score in the period, up to a page, for the trends. Newest first is the
 * endpoint's own order, so a window too dense to fit is cut at its far end and
 * the trend covers the most recent stretch of the period.
 */
export function fetchScoreHistory(
	userId: string,
	accessToken: string,
	period: Period
): Promise<ScorePage> {
	return apiGet<ScorePage>(`${path(userId)}?${eventWindow(period, SUMMARY_CAP)}`, accessToken);
}

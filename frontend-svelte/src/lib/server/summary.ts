import { apiGet } from './api';
import type { DataSummary, DataTimeline } from '$lib/summary/types';
import { periodBucket, periodWindow, type Period } from '$lib/summary/period';

const stamp = (date: Date) => `${date.toISOString().slice(0, 19)}Z`;

/** Omitted bounds mean the whole history, which is what "All time" asks for. */
function windowParams(period: Period, extra: Record<string, string> = {}) {
	const params = new URLSearchParams(extra);
	const window = periodWindow(period);
	if (window) {
		params.set('start_date', stamp(window.from));
		params.set('end_date', stamp(window.to));
	}
	return params;
}

export const fetchDataSummary = (userId: string, accessToken: string, period: Period) =>
	apiGet<DataSummary>(
		`/api/v1/users/${userId}/summaries/data?${windowParams(period)}`,
		accessToken
	);

export const fetchDataTimeline = (
	userId: string,
	accessToken: string,
	period: Period,
	groupBy: 'provider' | 'series_type'
) =>
	apiGet<DataTimeline>(
		`/api/v1/users/${userId}/summaries/data/timeline?${windowParams(period, {
			bucket: periodBucket(period),
			group_by: groupBy
		})}`,
		accessToken
	);

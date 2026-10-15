import { apiGet } from './api';
import type { BodySummary } from '$lib/body/types';

/**
 * Seven days, not one: a resting pulse and an HRV wander enough day to day that
 * a single reading says more about when it was taken than about the person.
 */
const AVERAGE_DAYS = 7;

/**
 * How recent a point-in-time reading has to be to be worth showing. The default
 * is four hours; a day is the useful span for an admin checking what arrived.
 */
const LATEST_WINDOW_HOURS = 24;

/** Null when this user has no body data at all, which the caller has to handle. */
export const fetchBody = (userId: string, accessToken: string) =>
	apiGet<BodySummary | null>(
		`/api/v1/users/${userId}/summaries/body?average_period=${AVERAGE_DAYS}&latest_window_hours=${LATEST_WINDOW_HOURS}`,
		accessToken
	);

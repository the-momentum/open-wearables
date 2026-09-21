import { periodWindow, type Period } from '$lib/filters/period';

/**
 * The event endpoints require both bounds, unlike the summaries, so "All time"
 * has to name one. Unix 0 is the honest way to say "from the beginning".
 */
const ALL_TIME_START = '0';

const stamp = (date: Date) => `${date.toISOString().slice(0, 19)}Z`;

/** Tomorrow UTC, so anything from today is inside the half-open window. */
function tomorrow(): Date {
	const date = new Date();
	date.setUTCHours(0, 0, 0, 0);
	date.setUTCDate(date.getUTCDate() + 1);
	return date;
}

/**
 * Timestamps, never bare dates: the backend widens a date-only `end_date` to the
 * next midnight, and `periodWindow` has already done that — sending a date would
 * widen an already-widened bound and stretch every window by a day.
 */
export function eventWindow(period: Period, limit: number): URLSearchParams {
	const window = periodWindow(period);

	return new URLSearchParams({
		start_date: window ? stamp(window.from) : ALL_TIME_START,
		end_date: stamp(window ? window.to : tomorrow()),
		limit: String(limit)
	});
}

/** The most either list endpoint hands over at once, and what a summary may cost. */
export const SUMMARY_CAP = 1000;

/**
 * A provider this user has no connection to is a typo, not a filter: the API
 * takes a `ProviderName` enum, so forwarding one 422s the whole page. Keeping
 * only what they actually have is also the list the control offers.
 */
export const knownProvider = (connections: { provider: string }[], asked: string) =>
	connections.some((connection) => connection.provider === asked) ? asked : '';

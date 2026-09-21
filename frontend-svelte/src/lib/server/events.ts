import { parsePeriod, periodWindow, type Period } from '$lib/filters/period';

/** The envelope every cursor-paged list endpoint returns. */
export type Page<Item> = {
	data: Item[];
	pagination: { total_count: number | null; has_more: boolean };
};

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

/**
 * A summary endpoint: sum every record in the period, in its own request because
 * no list endpoint has an aggregate to ask and the cards must not wait for it.
 * `has_more` rides along because it is the only honest "there was more" signal
 * on the endpoints that return no count.
 */
export async function summaryOf<Item, Totals>(
	url: URL,
	fetchPage: (period: Period, limit: number) => Promise<Page<Item>>,
	sum: (items: Item[], total: number | null, hasMore: boolean) => Totals
): Promise<Totals> {
	const page = await fetchPage(parsePeriod(url.searchParams), SUMMARY_CAP);
	return sum(page.data, page.pagination.total_count, page.pagination.has_more);
}

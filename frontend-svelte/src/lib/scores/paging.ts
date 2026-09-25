import { DAY_MS } from '$lib/filters/period';

export type DayWindow = { from: Date; to: Date };

/**
 * A page is a stretch of days, because a card is a day: paging by record — what
 * the endpoint itself offers — made a page of twenty two cards for a provider
 * that scores every half hour, and twenty for one that scores once.
 */
export const dayCount = ({ from, to }: DayWindow): number =>
	Math.max(Math.round((to.getTime() - from.getTime()) / DAY_MS), 1);

export const dayPages = (period: DayWindow, size: number): number =>
	Math.max(Math.ceil(dayCount(period) / size), 1);

/** Page one is the newest stretch, which is where a reader opens the tab. */
export function dayWindow(period: DayWindow, at: number, size: number): DayWindow {
	const end = period.to.getTime() - (at - 1) * size * DAY_MS;
	const start = Math.max(end - size * DAY_MS, period.from.getTime());

	// A page past the end of the period would otherwise invert the window.
	return { from: new Date(start), to: new Date(Math.max(end, start + DAY_MS)) };
}

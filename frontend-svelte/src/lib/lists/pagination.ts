export const PAGE_SIZES = [10, 20, 50, 100] as const;
export type PageSize = (typeof PAGE_SIZES)[number];

export const DEFAULT_PAGE_SIZE: PageSize = 20;

export function isPageSize(value: unknown): value is PageSize {
	return PAGE_SIZES.includes(value as PageSize);
}

/**
 * Keeps the first visible item visible, rather than resetting to page 1 and
 * losing the reader's place. Can exceed the new page count if the total has
 * shrunk — the loader clamps that, since only it knows the total.
 */
export function pageForSize(page: number, from: PageSize | number, to: PageSize | number): number {
	const firstVisibleIndex = (Math.max(page, 1) - 1) * from;
	return Math.floor(firstVisibleIndex / to) + 1;
}

export type PageItem = number | 'gap';

/**
 * First, last, and a window around the current page, with gaps for the rest. A
 * gap hiding a single page shows that page instead: "1 … 3 … 5" spends an
 * ellipsis to save nothing.
 */
export function paginationItems(current: number, pages: number, around = 1): PageItem[] {
	if (pages < 1) return [];

	const shown = new Set<number>([1, pages]);
	for (let page = current - around; page <= current + around; page++) {
		if (page >= 1 && page <= pages) shown.add(page);
	}

	const items: PageItem[] = [];
	let previous = 0;

	for (const page of [...shown].sort((a, b) => a - b)) {
		if (previous) {
			if (page - previous === 2) items.push(previous + 1);
			else if (page - previous > 2) items.push('gap');
		}
		items.push(page);
		previous = page;
	}

	return items;
}

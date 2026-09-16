import { describe, expect, it } from 'vitest';
import { isPageSize, pageForSize, paginationItems } from './pagination';

describe('paginationItems', () => {
	it.each([
		[1, 0, []],
		[1, 1, [1]],
		[2, 3, [1, 2, 3]],
		[1, 5, [1, 2, 'gap', 5]],
		[5, 10, [1, 'gap', 4, 5, 6, 'gap', 10]],
		[2, 10, [1, 2, 3, 'gap', 10]],
		[9, 10, [1, 'gap', 8, 9, 10]]
	])('page %i of %i renders %j', (current, pages, expected) => {
		expect(paginationItems(current, pages)).toEqual(expected);
	});

	// "1 … 3 … 5" would spend an ellipsis to hide one page.
	it('shows a lone hidden page instead of a gap', () => {
		expect(paginationItems(1, 4, 1)).toEqual([1, 2, 3, 4]);
	});

	it('never exceeds seven items, however many pages there are', () => {
		for (const pages of [50, 500, 5000]) {
			for (const current of [1, 2, Math.floor(pages / 2), pages - 1, pages]) {
				expect(paginationItems(current, pages).length).toBeLessThanOrEqual(7);
			}
		}
	});

	it('always offers the first and last page as a way out', () => {
		const items = paginationItems(250, 500);
		expect(items[0]).toBe(1);
		expect(items.at(-1)).toBe(500);
	});
});

describe('pageForSize', () => {
	it('keeps the first page first, whatever the size', () => {
		expect(pageForSize(1, 20, 50)).toBe(1);
		expect(pageForSize(1, 100, 20)).toBe(1);
	});

	// Items 81-100 are on screen; at 50 per page they sit on page 2 (51-100).
	it('keeps the first visible item visible when the size grows', () => {
		expect(pageForSize(5, 20, 50)).toBe(2);
	});

	// Items 101-200 are on screen; at 20 per page item 101 starts page 6.
	it('keeps the first visible item visible when the size shrinks', () => {
		expect(pageForSize(2, 100, 20)).toBe(6);
	});

	it('is a no-op when the size does not change', () => {
		for (const page of [1, 2, 7, 250]) expect(pageForSize(page, 20, 20)).toBe(page);
	});

	it('never returns a page below one, even for a nonsense input', () => {
		for (const page of [0, -3]) expect(pageForSize(page, 20, 50)).toBe(1);
	});

	// The first visible item must land on the returned page, by construction.
	it('always lands on a page that still contains that item', () => {
		for (const page of [1, 2, 3, 9, 40]) {
			for (const from of [20, 50, 100] as const) {
				for (const to of [20, 50, 100] as const) {
					const firstVisible = (page - 1) * from + 1;
					const landed = pageForSize(page, from, to);
					expect(firstVisible).toBeGreaterThan((landed - 1) * to);
					expect(firstVisible).toBeLessThanOrEqual(landed * to);
				}
			}
		}
	});
});

describe('isPageSize', () => {
	it.each([
		[10, true],
		[20, true],
		[50, true],
		[100, true],
		[9, false],
		[15, false],
		[1000, false],
		['20', false],
		[null, false]
	])('treats %o as %s', (value, expected) => {
		expect(isPageSize(value)).toBe(expected);
	});
});

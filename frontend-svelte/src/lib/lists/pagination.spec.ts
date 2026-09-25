import { describe, expect, it } from 'vitest';
import { cursorHrefs } from './cursor';
import { offsetHrefs } from './offset';
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

const at = (search: string) => cursorHrefs(new URL(`https://x/users/1/workouts${search}`));

describe('cursorHrefs', () => {
	it('reads the position from the URL and refuses a nonsense one', () => {
		expect(at('?at=3').at).toBe(3);
		expect(at('').at).toBe(1);
		expect(at('?at=-2').at).toBe(1);
	});

	// A cursor names a position in one query, so a filter change has to drop it
	// or page three of the old list answers for page one of the new one.
	it('drops the cursor and the counter when a filter changes', () => {
		expect(at('?cursor=abc&at=4&provider=oura').hrefFor({ type: 'running' })).toBe(
			'/users/1/workouts?provider=oura&type=running'
		);
	});

	// Page one reached by a prev_ cursor has nothing before it, so the API reports
	// has_more false and withholds the forward cursor too — both arrows go dead.
	it('steps back to page one as the bare URL, not as a cursor', () => {
		expect(at('?cursor=page2&at=2').stepHref('prev_x', -1)).toBe('/users/1/workouts');
	});

	it('carries the cursor and the next position forward', () => {
		expect(at('?at=2&cursor=page2').stepHref('next_x', 1)).toBe(
			'/users/1/workouts?at=3&cursor=next_x'
		);
	});

	it('has nowhere to step when the API offered no cursor', () => {
		expect(at('?at=3&cursor=page3').stepHref(null, 1)).toBeNull();
	});
});

describe('offsetHrefs', () => {
	const hrefs = offsetHrefs(new URL('http://x/syncs?status=failed&page=3&size=50'));

	it('sends any filter change back to page one', () => {
		expect(hrefs.hrefFor({ status: 'partial' })).toBe('/syncs?status=partial&size=50');
		expect(hrefs.sizeHref(20)).toBe('/syncs?status=failed&size=20');
	});

	// Page one is the bare URL, so both ways of reaching it share a link.
	it('keeps the filters when paging, and leaves page one out', () => {
		expect(hrefs.pageHref(4)).toBe('/syncs?status=failed&page=4&size=50');
		expect(hrefs.pageHref(1)).toBe('/syncs?status=failed&size=50');
	});
});

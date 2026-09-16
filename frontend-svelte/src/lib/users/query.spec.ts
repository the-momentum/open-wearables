import { describe, expect, it } from 'vitest';
import {
	hasActiveFilters,
	parseUsersQuery,
	toggleProvider,
	usersQueryHref,
	usersQueryToSearchParams,
	withPageSize,
	withUsersQuery,
	type UsersQuery
} from './query';

const BASE: UsersQuery = {
	page: 1,
	size: 20,
	search: '',
	sort: 'created_at',
	order: 'desc',
	providers: []
};

const parse = (search: string) => parseUsersQuery(new URLSearchParams(search));

describe('parseUsersQuery', () => {
	it('defaults to the first page sorted by newest, unfiltered', () => {
		expect(parse('')).toEqual(BASE);
	});

	it('reads every supported parameter', () => {
		expect(parse('page=3&size=50&search=kowalski&sort=name&order=asc&provider=oura')).toEqual({
			page: 3,
			size: 50,
			search: 'kowalski',
			sort: 'name',
			order: 'asc',
			providers: ['oura']
		});
	});

	it('collects a repeated provider parameter', () => {
		expect(parse('provider=garmin&provider=oura').providers).toEqual(['garmin', 'oura']);
	});

	// Otherwise the same selection reached two ways would be two cache keys.
	it('sorts and de-duplicates providers so one selection is one URL', () => {
		expect(parse('provider=oura&provider=garmin&provider=oura').providers).toEqual([
			'garmin',
			'oura'
		]);
	});

	// A hand-edited or stale URL must render a page, not an error.
	it.each(['sort=havoc', 'order=sideways', 'page=0', 'page=-4', 'page=abc', 'size=7', 'size=abc'])(
		'falls back to a default for %s',
		(bad) => {
			expect(() => parse(bad)).not.toThrow();
			expect(parse(bad)).toMatchObject({ page: expect.any(Number) });
		}
	);

	it('trims the search term so a stray space is not a different query', () => {
		expect(parse('search=%20%20ola%20%20').search).toBe('ola');
	});
});

describe('usersQueryToSearchParams', () => {
	it('omits defaults so a plain /users URL stays clean', () => {
		expect(usersQueryToSearchParams(BASE).toString()).toBe('');
		expect(usersQueryHref(BASE)).toBe('/users');
	});

	it('round-trips a non-default query', () => {
		const query: UsersQuery = {
			...BASE,
			page: 2,
			size: 100,
			search: 'ola',
			sort: 'name',
			order: 'asc',
			providers: ['garmin', 'whoop']
		};
		expect(parseUsersQuery(usersQueryToSearchParams(query))).toEqual(query);
	});
});

describe('withUsersQuery', () => {
	const current: UsersQuery = { ...BASE, page: 5 };

	// Otherwise a search from page 5 lands on an empty page 5 of the new results.
	it('returns to the first page when the filter changes', () => {
		expect(withUsersQuery(current, { search: 'ola' }).page).toBe(1);
		expect(withUsersQuery(current, { sort: 'name' }).page).toBe(1);
	});

	it('keeps the page when the page is what changed', () => {
		expect(withUsersQuery(current, { page: 6 }).page).toBe(6);
	});
});

describe('toggleProvider', () => {
	it('adds a provider and returns to the first page', () => {
		const next = toggleProvider({ ...BASE, page: 4 }, 'oura');
		expect(next.providers).toEqual(['oura']);
		expect(next.page).toBe(1);
	});

	it('removes a provider that is already selected', () => {
		expect(toggleProvider({ ...BASE, providers: ['garmin', 'oura'] }, 'garmin').providers).toEqual([
			'oura'
		]);
	});
});

describe('hasActiveFilters', () => {
	it.each([
		[BASE, false],
		[{ ...BASE, page: 3 }, false],
		[{ ...BASE, search: 'ola' }, true],
		[{ ...BASE, providers: ['oura'] }, true]
	])('reports %o as %s', (query, expected) => {
		expect(hasActiveFilters(query)).toBe(expected);
	});
});

describe('withPageSize', () => {
	// Someone changes the size while deep in the list; their place is kept.
	it('recomputes the page instead of resetting to the first', () => {
		const next = withPageSize({ ...BASE, page: 5, size: 20 }, 50);
		expect(next).toMatchObject({ page: 2, size: 50 });
	});

	it('keeps every other part of the query', () => {
		const query: UsersQuery = { ...BASE, page: 3, search: 'ola', providers: ['oura'] };
		expect(withPageSize(query, 50)).toMatchObject({ search: 'ola', providers: ['oura'] });
	});

	it('round-trips through the URL', () => {
		const next = withPageSize({ ...BASE, page: 5, size: 20 }, 50);
		expect(parseUsersQuery(usersQueryToSearchParams(next))).toEqual(next);
	});
});

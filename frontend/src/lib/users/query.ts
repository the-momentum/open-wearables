import { resolve } from '$app/paths';
import { DEFAULT_PAGE_SIZE, isPageSize, pageForSize, type PageSize } from '$lib/lists/pagination';
import type { SortOrder } from '$lib/lists/types';

export const SORT_FIELDS = ['created_at', 'name', 'email', 'last_synced_at'] as const;
export type SortField = (typeof SORT_FIELDS)[number];

export type UsersQuery = {
	page: number;
	size: PageSize;
	search: string;
	sort: SortField;
	order: SortOrder;
	providers: string[];
};

/** Not last_synced_at: it is the one sort that aggregates before LIMIT. */
const DEFAULTS: UsersQuery = {
	page: 1,
	size: DEFAULT_PAGE_SIZE,
	search: '',
	sort: 'created_at',
	order: 'desc',
	providers: []
};

function toInt(value: string | null, fallback: number): number {
	const parsed = Number(value);
	return Number.isInteger(parsed) && parsed >= 1 ? parsed : fallback;
}

/** Anything unrecognised falls back to the default rather than erroring. */
export function parseUsersQuery(params: URLSearchParams): UsersQuery {
	const sort = params.get('sort');
	const order = params.get('order');

	const size = Number(params.get('size'));

	return {
		page: toInt(params.get('page'), DEFAULTS.page),
		size: isPageSize(size) ? size : DEFAULTS.size,
		search: params.get('search')?.trim() ?? DEFAULTS.search,
		sort: SORT_FIELDS.includes(sort as SortField) ? (sort as SortField) : DEFAULTS.sort,
		order: order === 'asc' || order === 'desc' ? order : DEFAULTS.order,
		// Sorted and de-duplicated so the same selection is always the same URL.
		providers: [...new Set(params.getAll('provider').filter(Boolean))].sort()
	};
}

/** Only non-default values, so a plain /users URL stays clean. */
export function usersQueryToSearchParams(query: UsersQuery): URLSearchParams {
	const params = new URLSearchParams();
	if (query.page !== DEFAULTS.page) params.set('page', String(query.page));
	if (query.size !== DEFAULTS.size) params.set('size', String(query.size));
	if (query.search) params.set('search', query.search);
	if (query.sort !== DEFAULTS.sort) params.set('sort', query.sort);
	if (query.order !== DEFAULTS.order) params.set('order', query.order);
	for (const provider of query.providers) params.append('provider', provider);
	return params;
}

/** Changing anything but the page returns to the first one. */
export function withUsersQuery(current: UsersQuery, changes: Partial<UsersQuery>): UsersQuery {
	const next = { ...current, ...changes };
	return 'page' in changes ? next : { ...next, page: 1 };
}

/**
 * Changing the size keeps the reader's place rather than resetting to page 1;
 * `withUsersQuery` cannot do this because it only sees the change, not the
 * size it is replacing.
 */
export function withPageSize(current: UsersQuery, size: PageSize): UsersQuery {
	return { ...current, size, page: pageForSize(current.page, current.size, size) };
}

export function toggleProvider(query: UsersQuery, provider: string): UsersQuery {
	const providers = query.providers.includes(provider)
		? query.providers.filter((name) => name !== provider)
		: [...query.providers, provider].sort();
	return withUsersQuery(query, { providers });
}

export function usersQueryHref(query: UsersQuery): string {
	const params = usersQueryToSearchParams(query).toString();
	const path = resolve('/users');
	return params ? `${path}?${params}` : path;
}

export function hasActiveFilters(query: UsersQuery): boolean {
	return Boolean(query.search) || query.providers.length > 0;
}

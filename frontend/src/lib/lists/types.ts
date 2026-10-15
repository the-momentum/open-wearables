export type SortOrder = 'asc' | 'desc';

/** The envelope every list endpoint returns (backend `OldPaginatedResponse`). */
export type Page = {
	total: number;
	page: number;
	limit: number;
	pages: number;
	has_next: boolean;
	has_prev: boolean;
};

export type Paginated<T> = Page & { items: T[] };

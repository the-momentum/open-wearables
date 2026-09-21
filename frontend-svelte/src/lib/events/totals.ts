/** Adds up one field across records, treating a missing value as nothing. */
export const sumOf = <T>(items: T[], pick: (item: T) => number | null) =>
	items.reduce((sum, item) => sum + (pick(item) ?? 0), 0);

/**
 * No list endpoint has an aggregate to ask, so the figures are summed from the
 * records — and the API's own `has_more` is what says it held some back. A count
 * comparison misses it entirely on the endpoints that return no count at all.
 */
export const isPartial = (hasMore: boolean) => hasMore;

/** The mean of the records that reported the field, not of all of them. */
export function meanOf<T>(items: T[], pick: (item: T) => number | null): number | null {
	const values = items.map(pick).filter((value): value is number => value !== null);
	return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
}

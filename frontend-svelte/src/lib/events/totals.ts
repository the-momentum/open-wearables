/** Adds up one field across records, treating a missing value as nothing. */
export const sumOf = <T>(items: T[], pick: (item: T) => number | null) =>
	items.reduce((sum, item) => sum + (pick(item) ?? 0), 0);

/**
 * Neither list endpoint has an aggregate to ask, so the figures are summed from
 * the records — and this says when the API held more than one page could carry.
 * The count beside them is the API's own and stays exact either way.
 */
export const isPartial = (summed: number, total: number | null) => total !== null && total > summed;

/** The mean of the records that reported the field, not of all of them. */
export function meanOf<T>(items: T[], pick: (item: T) => number | null): number | null {
	const values = items.map(pick).filter((value): value is number => value !== null);
	return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
}

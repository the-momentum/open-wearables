/**
 * Both priority lists are the same list under a different key, so the ordering
 * works on whatever identifies a row and the caller says what that is.
 */
export function moved<T>(items: T[], index: number, delta: number): T[] {
	const target = index + delta;
	if (target < 0 || target >= items.length) return items;

	const next = [...items];
	[next[index], next[target]] = [next[target], next[index]];
	return next;
}

/** True once the reader has actually changed the order, not merely touched it. */
export const reordered = <T>(items: T[], original: T[], key: (item: T) => string): boolean =>
	items.length !== original.length ||
	items.some((item, index) => key(item) !== key(original[index]));

/**
 * Position in the list is the priority, counted from 1 — the API stores a
 * number per row, and sending the index keeps the two from drifting apart.
 */
export const ranked = <T, K extends string>(items: T[], key: K, of: (item: T) => string) =>
	items.map((item, index) => ({ [key]: of(item), priority: index + 1 }));

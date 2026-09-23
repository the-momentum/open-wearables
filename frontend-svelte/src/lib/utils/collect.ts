/**
 * Group items by a key, keeping the order they arrived in — both the order of
 * the groups and of the items inside them. Hand-rolled five times over three
 * files before this existed, twice with `[...(map.get(key) ?? []), item]`, which
 * copies the whole group on every item.
 */
export function collect<T>(items: T[], key: (item: T) => string): Map<string, T[]> {
	const groups = new Map<string, T[]>();

	for (const item of items) {
		const own = groups.get(key(item));
		if (own) own.push(item);
		else groups.set(key(item), [item]);
	}

	return groups;
}

/** The same grouping as a list, which is what an `{#each}` wants. */
export function grouped<T>(items: T[], key: (item: T) => string): { key: string; items: T[] }[] {
	return [...collect(items, key).entries()].map(([group, own]) => ({ key: group, items: own }));
}

/** Membership toggled, as a new array: what every row of chips does on click. */
export const toggled = <T>(list: T[], value: T): T[] =>
	list.includes(value) ? list.filter((entry) => entry !== value) : [...list, value];

/** Every one of `values` in the list, or none of them — a group's all / none. */
export function withAll<T>(list: T[], values: T[], on: boolean): T[] {
	const rest = list.filter((entry) => !values.includes(entry));
	return on ? [...rest, ...values] : rest;
}

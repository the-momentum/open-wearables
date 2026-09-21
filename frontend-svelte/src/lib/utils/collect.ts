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

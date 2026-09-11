/** Merge query changes into the current URL; a null value drops the key. */
export function withParams(url: URL, changes: Record<string, string | null>): string {
	const next = new URL(url);
	for (const [key, value] of Object.entries(changes)) {
		if (value === null) next.searchParams.delete(key);
		else next.searchParams.set(key, value);
	}
	return `${next.pathname}${next.search}`;
}

import { withParams } from '$lib/utils/url';

/**
 * Keyset paging for a list whose endpoint hands out cursors. `at` rides in the
 * URL purely so the reader can see where they are: a cursor carries no ordinal,
 * and there is no way to ask for page seven.
 *
 * `key` is the parameter the endpoint reads it under — `cursor` on the event
 * lists, `iterator` on anything coming through Svix.
 */
export function cursorHrefs(url: URL, key = 'cursor') {
	const at = Math.max(Number(url.searchParams.get('at') ?? 1), 1);

	// A cursor names a position in one query, so any filter change drops it — and
	// the counter with it — or page three of the old list answers for page one of
	// the new one.
	const hrefFor = (changes: Record<string, string | null>) =>
		withParams(url, { [key]: null, at: null, ...changes });

	function stepHref(cursor: string | null, delta: number) {
		// Page one is the bare URL, never a backward cursor. Reached by cursor it
		// has nothing before it, so the API reports has_more false and withholds
		// the forward cursor with it, stranding the reader with both arrows dead.
		if (at + delta === 1) return hrefFor({});
		return cursor === null ? null : withParams(url, { [key]: cursor, at: String(at + delta) });
	}

	return { at, hrefFor, stepHref };
}

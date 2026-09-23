import type { PageSize } from './pagination';
import { withParams } from '$lib/utils/url';

/**
 * Numbered paging kept in the URL. Any filter change returns to page one:
 * page five of the old list would otherwise answer for page one of the new one.
 */
export function offsetHrefs(url: URL) {
	const hrefFor = (changes: Record<string, string | null>) =>
		withParams(url, { page: null, ...changes });
	const pageHref = (at: number) => withParams(url, { page: at === 1 ? null : String(at) });
	const sizeHref = (size: PageSize) => hrefFor({ size: String(size) });

	return { hrefFor, pageHref, sizeHref };
}

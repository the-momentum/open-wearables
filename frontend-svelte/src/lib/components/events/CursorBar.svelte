<script lang="ts">
	import Pagination from '$lib/components/ui/Pagination.svelte';
	import type { cursorHrefs } from '$lib/lists/cursor';
	import type { PageSize } from '$lib/lists/pagination';

	let {
		nav,
		pagination,
		size
	}: {
		nav: ReturnType<typeof cursorHrefs>;
		/**
		 * Straight from the API. `total_count` is passed through untouched: some of
		 * these endpoints do not count, and substituting the page length there made
		 * the bar claim one page while its own next arrow still worked.
		 */
		pagination: {
			total_count: number | null;
			next_cursor: string | null;
			previous_cursor: string | null;
		};
		size: number;
	} = $props();

	const sizeHref = (next: PageSize) => nav.hrefFor({ size: String(next) });
</script>

<!-- No `hrefFor`: these endpoints page by cursor, so there is no page seven to
     link to and the bar marks the position instead. -->
<Pagination
	page={nav.at}
	{size}
	total={pagination.total_count}
	previousHref={nav.stepHref(pagination.previous_cursor, -1)}
	nextHref={nav.stepHref(pagination.next_cursor, 1)}
	sizeHrefFor={sizeHref}
/>

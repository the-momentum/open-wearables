<script lang="ts">
	import ChevronLeft from '@lucide/svelte/icons/chevron-left';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import { paginationItems, type PageSize } from '$lib/lists/pagination';
	import type { Page } from '$lib/lists/types';
	import { cn } from '$lib/utils/cn';
	import PageSizeSelect from './PageSizeSelect.svelte';

	let {
		page,
		hrefFor,
		sizeHrefFor,
		label = 'Pagination'
	}: {
		page: Page;
		hrefFor: (page: number) => string;
		/** Omit to hide the page-size control. */
		sizeHrefFor?: (size: PageSize) => string;
		/** Distinguishes the bars when one appears above the list and one below. */
		label?: string;
	} = $props();

	const first = $derived((page.page - 1) * page.limit + 1);
	const last = $derived(Math.min(page.page * page.limit, page.total));
	const items = $derived(paginationItems(page.page, page.pages));

	const step =
		'border-border hover:bg-surface-muted grid size-10 place-items-center rounded-lg border transition-colors';
	const spent =
		'border-border text-muted-foreground/40 grid size-10 place-items-center rounded-lg border';
</script>

<!-- Hrefs come from the caller, which resolves them. -->
<!-- eslint-disable svelte/no-navigation-without-resolve -->
<nav class="flex flex-wrap items-center justify-between gap-3" aria-label={label}>
	<div class="flex flex-wrap items-center gap-x-4 gap-y-2">
		<p class="text-sm text-muted-foreground" aria-live="polite">
			{#if page.total === 0}
				No results
			{:else}
				<span class="font-medium text-foreground">{first}–{last}</span> of {page.total}
			{/if}
		</p>

		{#if sizeHrefFor}
			<PageSizeSelect size={page.limit} hrefFor={sizeHrefFor} />
		{/if}
	</div>

	<div class="flex items-center gap-1.5">
		{#if page.has_prev}
			<a href={hrefFor(page.page - 1)} rel="prev" aria-label="Previous page" class={step}>
				<ChevronLeft size={18} aria-hidden="true" />
			</a>
		{:else}
			<span class={spent} aria-hidden="true"><ChevronLeft size={18} /></span>
		{/if}

		<!-- Numbers need room; the small screen keeps the plain counter. -->
		<span class="px-1 text-sm text-muted-foreground tabular-nums sm:hidden">
			{page.page} / {Math.max(page.pages, 1)}
		</span>

		<ul class="hidden items-center gap-1 sm:flex">
			{#each items as item, index (item === 'gap' ? `gap-${index}` : item)}
				<li>
					{#if item === 'gap'}
						<span class="grid size-10 place-items-center text-sm text-muted-foreground/60">…</span>
					{:else}
						<a
							href={hrefFor(item)}
							aria-label="Page {item}"
							aria-current={item === page.page ? 'page' : undefined}
							class={cn(
								'grid size-10 place-items-center rounded-lg border text-sm tabular-nums transition-colors',
								item === page.page
									? 'border-primary/40 bg-primary/10 font-medium text-primary'
									: 'border-border hover:bg-surface-muted'
							)}
						>
							{item}
						</a>
					{/if}
				</li>
			{/each}
		</ul>

		{#if page.has_next}
			<a href={hrefFor(page.page + 1)} rel="next" aria-label="Next page" class={step}>
				<ChevronRight size={18} aria-hidden="true" />
			</a>
		{:else}
			<span class={spent} aria-hidden="true"><ChevronRight size={18} /></span>
		{/if}
	</div>
</nav>

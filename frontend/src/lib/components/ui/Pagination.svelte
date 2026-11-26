<script lang="ts">
	import ChevronLeft from '@lucide/svelte/icons/chevron-left';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import { paginationItems, type PageItem, type PageSize } from '$lib/lists/pagination';
	import { cn } from '$lib/utils/cn';
	import { ICON } from './icon';
	import PageSizeSelect from './PageSizeSelect.svelte';
	import { STEP, STEP_SPENT } from './typography';

	let {
		page,
		size,
		total,
		previousHref,
		nextHref,
		hrefFor,
		sizeHrefFor,
		noun = '',
		label = 'Pagination',
		placement
	}: {
		/** 1-based position, which both kinds of paging know. */
		page: number;
		size: number;
		/** Null where the endpoint does not count: there is then no last page. */
		total: number | null;
		previousHref: string | null;
		nextHref: string | null;
		/**
		 * Offset paging only. Keyset paging knows what comes next but not how to
		 * reach page seven, so without this the numbers are simply not offered.
		 */
		hrefFor?: (page: number) => string;
		/** Omit to hide the page-size control. */
		sizeHrefFor?: (size: PageSize) => string;
		/** What is being counted, where the list above does not make it obvious. */
		noun?: string;
		/** Distinguishes the bars when one appears above the list and one below. */
		label?: string;
		/**
		 * Of a pair round one list. A phone has room for half of each: the bar above
		 * keeps the range and page size, the one below the range and the steps.
		 */
		placement?: 'above' | 'below';
	} = $props();

	// An uncounted list has no last page, so it gets a position and nothing else:
	// claiming "of 1" while the next arrow still works is worse than saying less.
	const pages = $derived(total === null ? null : Math.max(Math.ceil(total / size), 1));
	const first = $derived((page - 1) * size + 1);
	const last = $derived(total === null ? page * size : Math.min(page * size, total));
	// A phone keeps only the current page between first and last, so the steps fit one row.
	const wide = $derived(hrefFor && pages !== null ? paginationItems(page, pages) : []);
	const narrow = $derived(hrefFor && pages !== null ? paginationItems(page, pages, 0) : []);

	const chip = (current: boolean) =>
		cn(
			STEP,
			'text-sm tabular-nums',
			current && 'border-primary/40 bg-primary/10 font-medium text-primary hover:bg-primary/10'
		);
</script>

<!-- Hrefs come from the caller, which resolves them. Every step is noscroll:
     this bar sits under the list, so jumping to the top of the page puts the
     control the reader just used out of reach. -->
<!-- eslint-disable svelte/no-navigation-without-resolve -->
{#snippet numbers(items: PageItem[], shown: string)}
	<ul class="items-center gap-1.5 {shown}">
		{#each items as item, index (item === 'gap' ? `gap-${index}` : item)}
			<li>
				{#if item === 'gap'}
					<span class="grid size-10 place-items-center text-sm text-muted-foreground">…</span>
				{:else}
					<a
						href={hrefFor?.(item)}
						aria-label="Page {item}"
						aria-current={item === page ? 'page' : undefined}
						data-sveltekit-noscroll
						class={chip(item === page)}
					>
						{item}
					</a>
				{/if}
			</li>
		{/each}
	</ul>
{/snippet}

<nav class="flex flex-wrap items-center justify-between gap-3" aria-label={label}>
	<div class="flex flex-wrap items-center gap-x-4 gap-y-2">
		<p class="text-sm text-muted-foreground" aria-live="polite">
			{#if total === 0}
				No results
			{:else if total === null}
				<span class="font-medium text-foreground">{first}–{last}</span>
			{:else}
				<span class="font-medium text-foreground">{first}–{last}</span> of {total}{noun
					? ` ${noun}`
					: ''}
			{/if}
		</p>

		{#if sizeHrefFor}
			<div class={cn(placement === 'below' && 'hidden sm:block')}>
				<PageSizeSelect {size} hrefFor={sizeHrefFor} />
			</div>
		{/if}
	</div>

	<div class={cn('items-center gap-1.5', placement === 'above' ? 'hidden sm:flex' : 'flex')}>
		{#if previousHref}
			<a
				href={previousHref}
				rel="prev"
				aria-label="Previous page"
				data-sveltekit-noscroll
				class={STEP}
			>
				<ChevronLeft size={ICON.md} aria-hidden="true" />
			</a>
		{:else}
			<span class={STEP_SPENT} aria-hidden="true"><ChevronLeft size={ICON.md} /></span>
		{/if}

		{#if wide.length}
			{@render numbers(narrow, 'flex sm:hidden')}
			{@render numbers(wide, 'hidden sm:flex')}
		{:else}
			<!-- Keyset paging can mark where you are but cannot link anywhere else:
			     a counter on a phone, the position's chip from sm up. -->
			<span class="px-1 text-sm text-muted-foreground tabular-nums sm:hidden">
				{pages === null ? page : `${page} / ${pages}`}
			</span>
			<span class="hidden items-center gap-2 sm:flex">
				<span aria-current="page" class={chip(true)}>{page}</span>
				{#if pages !== null}
					<span class="text-sm text-muted-foreground tabular-nums">of {pages}</span>
				{/if}
			</span>
		{/if}

		{#if nextHref}
			<a href={nextHref} rel="next" aria-label="Next page" data-sveltekit-noscroll class={STEP}>
				<ChevronRight size={ICON.md} aria-hidden="true" />
			</a>
		{:else}
			<span class={STEP_SPENT} aria-hidden="true"><ChevronRight size={ICON.md} /></span>
		{/if}
	</div>
</nav>

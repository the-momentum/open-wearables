<script lang="ts">
	import ChevronLeft from '@lucide/svelte/icons/chevron-left';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import { paginationItems, type PageSize } from '$lib/lists/pagination';
	import { cn } from '$lib/utils/cn';
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
		label = 'Pagination'
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
		/** Distinguishes the bars when one appears above the list and one below. */
		label?: string;
	} = $props();

	// An uncounted list has no last page, so it gets a position and nothing else:
	// claiming "of 1" while the next arrow still works is worse than saying less.
	const pages = $derived(total === null ? null : Math.max(Math.ceil(total / size), 1));
	const first = $derived((page - 1) * size + 1);
	const last = $derived(total === null ? page * size : Math.min(page * size, total));
	const items = $derived(hrefFor && pages !== null ? paginationItems(page, pages) : []);

	const chip = (current: boolean) =>
		cn(
			'grid size-10 place-items-center rounded-lg border text-sm tabular-nums transition-colors',
			current
				? 'border-primary/40 bg-primary/10 font-medium text-primary'
				: 'border-border hover:bg-surface-muted'
		);
</script>

<!-- Hrefs come from the caller, which resolves them. Every step is noscroll:
     this bar sits under the list, so jumping to the top of the page puts the
     control the reader just used out of reach. -->
<!-- eslint-disable svelte/no-navigation-without-resolve -->
<nav class="flex flex-wrap items-center justify-between gap-3" aria-label={label}>
	<div class="flex flex-wrap items-center gap-x-4 gap-y-2">
		<p class="text-sm text-muted-foreground" aria-live="polite">
			{#if total === 0}
				No results
			{:else if total === null}
				<span class="font-medium text-foreground">{first}–{last}</span>
			{:else}
				<span class="font-medium text-foreground">{first}–{last}</span> of {total}
			{/if}
		</p>

		{#if sizeHrefFor}
			<PageSizeSelect {size} hrefFor={sizeHrefFor} />
		{/if}
	</div>

	<div class="flex items-center gap-1.5">
		{#if previousHref}
			<a
				href={previousHref}
				rel="prev"
				aria-label="Previous page"
				data-sveltekit-noscroll
				class={STEP}
			>
				<ChevronLeft size={18} aria-hidden="true" />
			</a>
		{:else}
			<span class={STEP_SPENT} aria-hidden="true"><ChevronLeft size={18} /></span>
		{/if}

		<!-- Numbers need room, so the small screen keeps the plain counter. -->
		<span class="px-1 text-sm text-muted-foreground tabular-nums sm:hidden">
			{pages === null ? page : `${page} / ${pages}`}
		</span>

		{#if items.length}
			<ul class="hidden items-center gap-1 sm:flex">
				{#each items as item, index (item === 'gap' ? `gap-${index}` : item)}
					<li>
						{#if item === 'gap'}
							<span class="grid size-10 place-items-center text-sm text-muted-foreground/60">…</span
							>
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
		{:else}
			<!-- Keyset paging can mark where you are but cannot link anywhere else,
			     so the position wears the same chip with nothing beside it. -->
			<span class="hidden items-center gap-2 sm:flex">
				<span aria-current="page" class={chip(true)}>{page}</span>
				{#if pages !== null}
					<span class="text-sm text-muted-foreground tabular-nums">of {pages}</span>
				{/if}
			</span>
		{/if}

		{#if nextHref}
			<a href={nextHref} rel="next" aria-label="Next page" data-sveltekit-noscroll class={STEP}>
				<ChevronRight size={18} aria-hidden="true" />
			</a>
		{:else}
			<span class={STEP_SPENT} aria-hidden="true"><ChevronRight size={18} /></span>
		{/if}
	</div>
</nav>

<script lang="ts">
	import type { Snippet } from 'svelte';
	import ArrowDown from '@lucide/svelte/icons/arrow-down';
	import ArrowUp from '@lucide/svelte/icons/arrow-up';
	import ChevronsUpDown from '@lucide/svelte/icons/chevrons-up-down';
	import type { SortOrder } from '$lib/lists/types';
	import { ICON } from './icon';

	let {
		field,
		sort,
		order,
		hrefFor,
		children
	}: {
		field: string;
		sort: string;
		order: SortOrder;
		hrefFor: (field: string, order: SortOrder) => string;
		children: Snippet;
	} = $props();

	const active = $derived(sort === field);
	// A fresh column starts descending; the active one flips.
	const next: SortOrder = $derived(active && order === 'desc' ? 'asc' : 'desc');
</script>

<!-- Hrefs come from the caller, which resolves them. -->
<!-- eslint-disable svelte/no-navigation-without-resolve -->
<a
	href={hrefFor(field, next)}
	class="inline-flex items-center gap-1 transition-colors hover:text-foreground"
	class:text-foreground={active}
>
	{@render children()}
	{#if !active}
		<ChevronsUpDown size={ICON.xs} aria-hidden="true" />
	{:else if order === 'asc'}
		<ArrowUp size={ICON.xs} aria-hidden="true" />
	{:else}
		<ArrowDown size={ICON.xs} aria-hidden="true" />
	{/if}
</a>

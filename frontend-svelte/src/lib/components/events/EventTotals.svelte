<script lang="ts" generics="T extends { count: number; partial: boolean }">
	import type { Component } from 'svelte';
	import Figures from '$lib/components/ui/Figures.svelte';
	import Skeleton from '$lib/components/ui/Skeleton.svelte';
	import { resource } from '$lib/utils/resource.svelte';

	let {
		url,
		label,
		noun,
		figures
	}: {
		/** A function, so the caller's reactive reads happen inside the fetch. */
		url: () => string;
		label: string;
		noun: string;
		figures: (totals: T) => { icon: Component; label: string; value: string | number }[];
	} = $props();

	// Its own request, not part of the page load: summing a period reads every
	// record in it, and the cards below are what the reader came for.
	// Called through, not passed through: reading the prop straight would capture
	// the function this component was born with and never notice a new one.
	const summed = resource<T>(() => url());
	const totals = $derived(summed.current);
</script>

{#if totals}
	<Figures figures={figures(totals)} {label} />
{:else}
	<Skeleton class="h-[52px]" />
{/if}

{#if totals?.partial}
	<!-- Say it rather than quietly under-reporting: the count is exact, the sums
	     beside it are not, and an admin comparing them deserves to know which. -->
	<p class="mt-3 text-xs text-muted-foreground">
		Totals cover the most recent {noun} in this period, not all {totals.count}.
	</p>
{/if}

<script lang="ts">
	import ProviderLogo from '$lib/components/providers/ProviderLogo.svelte';
	import Badge from '$lib/components/ui/Badge.svelte';
	import { MICRO } from '$lib/components/ui/typography';
	import type { Capability } from '$lib/coverage/rows';
	import type { ProviderBrand } from '$lib/providers/labels';

	let {
		row,
		total,
		brandFor
	}: {
		row: Capability;
		/** Every provider there is, so "4 of 14" means something. */
		total: number;
		brandFor: (provider: string) => ProviderBrand;
	} = $props();
</script>

<!-- The supporters are named on the row rather than being dots under fourteen
     columns, which have to scroll sideways on a phone. -->
<div
	class="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-2 border-b border-border py-3
		last:border-b-0 sm:flex"
>
	<span class="flex min-w-0 items-baseline gap-2 sm:w-75 sm:shrink-0">
		<code class="truncate font-mono text-xs text-foreground" title={row.description || row.code}>
			{row.code}
		</code>
		{#if row.unit}<span class={MICRO}>{row.unit}</span>{/if}
	</span>

	<span class="col-span-2 row-start-2 flex flex-wrap items-center gap-1.5 sm:flex-1">
		{#each row.providers as provider (provider)}
			{@const brand = brandFor(provider)}
			<span title={brand.name}><ProviderLogo provider={brand} size="sm" /></span>
		{/each}
	</span>

	<span class="flex shrink-0 items-center justify-end gap-1.5 {MICRO} tabular-nums sm:w-24">
		<!-- One provider and no fallback: dropping that integration loses this
		     outright. -->
		{#if row.providers.length === 1}<Badge tone="warning">only</Badge>{/if}
		{row.providers.length} of {total}
	</span>
</div>

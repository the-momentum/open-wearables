<script lang="ts">
	import ProviderMark from '$lib/components/providers/ProviderMark.svelte';
	import Badge from '$lib/components/ui/Badge.svelte';
	import { MICRO } from '$lib/components/ui/typography';
	import type { Capability } from '$lib/coverage/rows';

	let {
		row,
		total,
		labelFor
	}: {
		row: Capability;
		/** Every provider there is, so "4 of 14" means something. */
		total: number;
		labelFor: (provider: string) => string;
	} = $props();
</script>

<!-- The supporters are named on the row rather than being dots under fourteen
     columns, which have to scroll sideways on a phone. -->
<div class="flex flex-wrap items-center gap-x-3 gap-y-1.5 py-2">
	<span class="flex min-w-0 flex-1 basis-48 items-baseline gap-2">
		<code class="truncate font-mono text-xs text-foreground" title={row.description || row.code}>
			{row.code}
		</code>
		{#if row.unit}<span class={MICRO}>{row.unit}</span>{/if}
	</span>

	<span class="flex flex-wrap items-center gap-1">
		{#each row.providers as provider (provider)}
			<span title={labelFor(provider)}>
				<ProviderMark {provider} label={labelFor(provider)} size="sm" />
			</span>
		{/each}
	</span>

	<span class="flex w-24 shrink-0 items-center justify-end gap-1.5 {MICRO} tabular-nums">
		<!-- One provider and no fallback: dropping that integration loses this
		     outright. -->
		{#if row.providers.length === 1}<Badge tone="warning">only</Badge>{/if}
		{row.providers.length} of {total}
	</span>
</div>

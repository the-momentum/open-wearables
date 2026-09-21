<script lang="ts">
	import type { Component, Snippet } from 'svelte';
	import MetricCell from './MetricCell.svelte';

	let {
		metrics,
		children
	}: {
		/** A fixed set per kind of card, so a column can be scanned down the list. */
		metrics: { icon: Component; label: string; value: string }[];
		/** A trailing cell for what a number cannot say — a stage mix, say. */
		children?: Snippet;
	} = $props();
</script>

<dl class="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4">
	{#each metrics as metric (metric.label)}
		<MetricCell icon={metric.icon} label={metric.label} value={metric.value} />
	{/each}
	{@render children?.()}
</dl>

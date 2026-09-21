<script lang="ts">
	import type { Component, Snippet } from 'svelte';
	import ChartRow from '$lib/components/ui/ChartRow.svelte';
	import Caption from '$lib/components/ui/Caption.svelte';
	import { MICRO } from '$lib/components/ui/typography';
	import { HEAT_STEPS } from '$lib/summary/shades';
	import { formatDuration } from '$lib/utils/format';

	let {
		title,
		icon: Icon,
		rows,
		unit,
		children
	}: {
		title: string;
		icon: Component;
		/** In the order they should read; `shade` overrides the default ramp. */
		rows: { label: string; seconds: number; shade?: string }[];
		unit?: string;
		/** A control sharing the heading's line — a kind switch, where there is one. */
		children?: Snippet;
	} = $props();

	const spent = $derived(rows.filter((row) => row.seconds > 0));
	const total = $derived(spent.reduce((sum, row) => sum + row.seconds, 0));
	const longest = $derived(Math.max(...spent.map((row) => row.seconds), 0));

	// First row palest: the ramp reads as intensity, which is what both callers
	// mean — effort climbing through zones, sleep deepening through stages.
	const shade = (row: { shade?: string }, index: number) =>
		row.shade ?? HEAT_STEPS[Math.min(index + 1, HEAT_STEPS.length - 1)];

	const share = (seconds: number) => (total === 0 ? 0 : Math.round((seconds / total) * 100));
</script>

{#if total > 0}
	<div class="flex flex-col gap-2">
		<div class="flex flex-wrap items-center justify-between gap-2">
			<Caption icon={Icon}>
				{title}
				{#if unit}<span class="normal-case">({unit})</span>{/if}
			</Caption>
			{@render children?.()}
		</div>

		<!-- The same label / track / value row as every other chart on the site, so
		     a distribution reads like a heatmap row rather than a bespoke widget. -->
		<div class="flex flex-col gap-1">
			{#each spent as row, index (row.label)}
				<ChartRow label={row.label} value={formatDuration(row.seconds)}>
					<div class="flex items-center gap-2">
						<span class="h-2.5 flex-1 overflow-hidden rounded-full bg-surface-muted">
							<span
								aria-hidden="true"
								class="block h-full rounded-full {shade(row, index)}"
								style="width: {longest === 0 ? 0 : (row.seconds / longest) * 100}%"
							></span>
						</span>
						<span class="w-8 shrink-0 text-right tabular-nums {MICRO}">
							{share(row.seconds)}%
						</span>
					</div>
				</ChartRow>
			{/each}
		</div>
	</div>
{/if}

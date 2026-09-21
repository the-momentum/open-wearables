<script lang="ts">
	import Sparkline from '$lib/components/charts/Sparkline.svelte';
	import Caption from '$lib/components/ui/Caption.svelte';
	import { MICRO } from '$lib/components/ui/typography';
	import { categorySpec } from '$lib/scores/categories';
	import type { CategoryTrend } from '$lib/scores/trends';
	import { showDecimal } from '$lib/utils/format';

	let {
		trend,
		from,
		to,
		colourFor,
		href
	}: {
		trend: CategoryTrend;
		/** The window every tile shares, so their shapes can be read against each other. */
		from: number;
		to: number;
		colourFor: (provider: string) => string;
		/** Null for a category the API cannot be asked to filter by. */
		href: string | null;
	} = $props();

	const spec = $derived(categorySpec(trend.category));
</script>

<!-- eslint-disable svelte/no-navigation-without-resolve -->
<svelte:element
	this={href ? 'a' : 'div'}
	{href}
	data-sveltekit-noscroll
	class="flex flex-col gap-2 rounded-xl border border-border bg-surface p-4 transition-colors
		{href ? 'hover:border-primary/40' : ''}"
>
	<div class="flex items-baseline justify-between gap-3">
		<Caption icon={spec.icon}>{spec.label}</Caption>

		<!-- Each provider's last word, in the colour of its own line: with two of
		     them the numbers are the comparison, and the line is how it got there. -->
		<span class="flex items-baseline gap-2">
			{#each trend.latest as entry (entry.provider)}
				<span
					class="text-lg font-semibold tabular-nums"
					style="color: {colourFor(entry.provider)}"
					title={entry.label}
				>
					{showDecimal(entry.value)}
				</span>
			{/each}
		</span>
	</div>

	<Sparkline lines={trend.lines} range={trend.range} {from} {to} {colourFor} />

	<div class="flex items-center justify-between gap-3 {MICRO}">
		<span class="flex min-w-0 flex-wrap items-center gap-x-2.5 gap-y-1">
			{#each trend.lines as line (line.type)}
				<span class="flex items-center gap-1.5">
					<span
						aria-hidden="true"
						class="size-1.5 shrink-0 rounded-full"
						style="background: {colourFor(line.type)}"
					></span>
					<span class="truncate">{line.label}</span>
				</span>
			{/each}
		</span>

		<!-- One range for every line in the tile: the scales differ by provider, so
		     a shared axis is the only way two heights mean the same thing. -->
		<span class="shrink-0 tabular-nums">
			{Math.round(trend.range.low)}–{Math.round(trend.range.high)}
		</span>
	</div>
</svelte:element>

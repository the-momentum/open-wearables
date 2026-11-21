<script lang="ts">
	import { arcs, DONUT_RING, donutSlices, leastArc, ringPath, slicePath } from '$lib/charts/donut';
	import { formatNumber, formatPercent } from '$lib/utils/format';
	import LegendItem from './LegendItem.svelte';

	let {
		parts,
		total,
		caption,
		label
	}: {
		/** Clockwise from twelve, in the order given; the first six get a hue each. */
		parts: { key: string; label: string; value: number }[];
		/** The whole the ring stands for: what the parts leave of it is drawn as "Other". */
		total: number;
		/** Under the total in the hole: what is being counted. */
		caption: string;
		label: string;
	} = $props();

	const { outer } = DONUT_RING;

	const slices = $derived(donutSlices(parts, total));
	const whole = $derived(slices.reduce((sum, slice) => sum + slice.value, 0));
	const paths = $derived(
		slices.length === 1
			? [ringPath(DONUT_RING)]
			: arcs(
					slices.map((slice) => slice.value),
					leastArc(DONUT_RING)
				).map((arc) => slicePath(arc, DONUT_RING))
	);

	let active = $state<string | null>(null);
	const dim = (key: string) => active !== null && active !== key;
</script>

<!-- The ring is a picture of the legend: every figure it shows is in the list as
     text, which is also what a screen reader gets. -->
{#if slices.length > 0}
	<div
		class="flex flex-col items-center gap-5 sm:flex-row sm:gap-8"
		role="group"
		aria-label={label}
	>
		<div class="relative size-42 shrink-0">
			<svg
				viewBox="{-outer} {-outer} {outer * 2} {outer * 2}"
				class="size-full overflow-visible"
				aria-hidden="true"
			>
				{#each slices as slice, index (slice.key)}
					<!-- Hover only highlights: the legend beside it says the same in text. -->
					<!-- svelte-ignore a11y_no_static_element_interactions -->
					<path
						d={paths[index]}
						fill={slice.colour}
						fill-rule="evenodd"
						class="transition-opacity duration-200 {dim(slice.key) ? 'opacity-30' : ''}"
						onpointerenter={() => (active = slice.key)}
						onpointerleave={() => (active = null)}
					/>
				{/each}
			</svg>

			<p class="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
				<span class="text-2xl font-medium text-foreground tabular-nums">{formatNumber(whole)}</span>
				<span class="text-xs text-muted-foreground">{caption}</span>
			</p>
		</div>

		<ul class="flex min-w-0 flex-col gap-2.5 self-stretch sm:gap-2 sm:self-center">
			{#each slices as slice (slice.key)}
				<li
					class="transition-opacity duration-200 {dim(slice.key) ? 'opacity-40' : ''}"
					onpointerenter={() => (active = slice.key)}
					onpointerleave={() => (active = null)}
				>
					<LegendItem
						size="md"
						label={slice.label}
						colour={slice.colour}
						value={formatNumber(slice.value)}
						share={formatPercent(slice.value, whole)}
					/>
				</li>
			{/each}
		</ul>
	</div>
{/if}

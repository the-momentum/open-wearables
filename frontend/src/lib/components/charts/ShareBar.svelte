<script lang="ts">
	import { rankShade } from '$lib/summary/shades';
	import { formatPercent } from '$lib/utils/format';
	import LegendItem from './LegendItem.svelte';

	export type Part = { key: string; label: string; value: number; shade?: string };

	let {
		parts,
		selected = '',
		value
	}: {
		/** Drawn in the order given; empty parts are left out. */
		parts: Part[];
		/** Dims the rest, so the bar still says how big the chosen slice is. */
		selected?: string;
		/** The figure beside each label, ahead of its share; the share alone without it. */
		value?: (part: Part) => string;
	} = $props();

	const shown = $derived(parts.filter((part) => part.value > 0));
	const total = $derived(shown.reduce((sum, part) => sum + part.value, 0));

	// One hue at descending strength unless the caller names its own: a ranking
	// has no good and bad ends, but "connected" and "not" do.
	const shadeOf = (part: Part, index: number) => part.shade ?? rankShade(index);
	const dim = (key: string) => selected !== '' && selected !== key;
</script>

{#if shown.length > 0}
	<div class="flex flex-col gap-2.5">
		<div class="flex h-3 gap-px overflow-hidden rounded-full bg-surface-muted">
			{#each shown as part, index (part.key)}
				<div
					class="{shadeOf(part, index)} transition-opacity {dim(part.key) ? 'opacity-20' : ''}"
					style:width="{(part.value / total) * 100}%"
					title="{part.label}: {part.value}"
				></div>
			{/each}
		</div>

		<ul class="flex flex-wrap gap-x-4 gap-y-1.5">
			{#each shown as part, index (part.key)}
				<li class="transition-opacity {dim(part.key) ? 'opacity-40' : ''}">
					<LegendItem
						label={part.label}
						shade={shadeOf(part, index)}
						value={value?.(part)}
						share={formatPercent(part.value, total)}
					/>
				</li>
			{/each}
		</ul>
	</div>
{/if}

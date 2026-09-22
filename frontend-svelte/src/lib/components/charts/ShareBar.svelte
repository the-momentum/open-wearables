<script lang="ts">
	import { rankShade } from '$lib/summary/shades';
	import { MICRO } from '$lib/components/ui/typography';

	export type Part = { key: string; label: string; value: number; shade?: string };

	let {
		parts,
		selected = '',
		format
	}: {
		/** Drawn in the order given; empty parts are left out. */
		parts: Part[];
		/** Dims the rest, so the bar still says how big the chosen slice is. */
		selected?: string;
		/** What to put beside each label — its share of the whole by default. */
		format?: (part: Part, total: number) => string;
	} = $props();

	const shown = $derived(parts.filter((part) => part.value > 0));
	const total = $derived(shown.reduce((sum, part) => sum + part.value, 0));
	const share = (value: number) => (total === 0 ? 0 : (value / total) * 100);

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
					style="width: {share(part.value)}%"
					title="{part.label}: {part.value}"
				></div>
			{/each}
		</div>

		<ul class="flex flex-wrap gap-x-4 gap-y-1.5">
			{#each shown as part, index (part.key)}
				<li
					class="flex items-center gap-1.5 text-xs transition-opacity
						{dim(part.key) ? 'opacity-40' : ''}"
				>
					<span aria-hidden="true" class="size-2 rounded-full {shadeOf(part, index)}"></span>
					<span class="text-foreground/80">{part.label}</span>
					<span class="{MICRO} tabular-nums">
						{format ? format(part, total) : `${share(part.value).toFixed(0)}%`}
					</span>
				</li>
			{/each}
		</ul>
	</div>
{/if}

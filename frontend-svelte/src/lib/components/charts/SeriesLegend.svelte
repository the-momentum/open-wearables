<script lang="ts">
	import { MICRO } from '$lib/components/ui/typography';
	import { seriesColour } from '$lib/timeseries/samples';

	let {
		lines,
		off,
		ontoggle,
		bands
	}: {
		lines: { type: string; label: string; dash: string }[];
		off: string[];
		ontoggle: (label: string) => void;
		/** What the shading behind the chart means, when there is any. */
		bands?: string;
	} = $props();

	// A dashed swatch for a dashed line: same colour, second device.
	const DASHED = 'mask: repeating-linear-gradient(90deg,#000 0 3px,transparent 3px 6px)';
</script>

<div class="flex flex-wrap items-center gap-x-3 gap-y-1.5">
	{#if bands}
		<span class={MICRO}>Bands: {bands.toLowerCase()} zones</span>
		<span aria-hidden="true" class="text-muted-foreground/30">|</span>
	{/if}

	{#each lines as line (line.label)}
		{@const on = !off.includes(line.label)}
		<button
			type="button"
			onclick={() => ontoggle(line.label)}
			aria-pressed={on}
			class="flex items-center gap-1.5 text-[11px] transition-opacity {on ? '' : 'opacity-40'}"
		>
			<span
				aria-hidden="true"
				class="h-0.5 w-4 rounded-full"
				style="background: {seriesColour(line.type)}; {line.dash ? DASHED : ''}"
			></span>
			<span class="text-foreground/80">{line.label}</span>
		</button>
	{/each}
</div>

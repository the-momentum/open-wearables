<script lang="ts">
	import { calendarTicks } from '$lib/charts/ticks';

	let {
		from,
		to
	}: {
		/** Start of the first bucket and end of the last, as epoch ms. */
		from: number;
		to: number;
	} = $props();

	// Measured, because how many labels fit is a question of pixels. Before the
	// first measurement (the server render) a desktop-ish width stands in.
	let width = $state(0);
	const ticks = $derived(calendarTicks(from, to, width || 720));
</script>

<div class="relative h-5" bind:clientWidth={width}>
	{#each ticks as tick (tick.at)}
		<span class="absolute bottom-0" style="left: {tick.at * 100}%">
			<span aria-hidden="true" class="absolute bottom-0 left-0 h-1 w-px bg-border"></span>
			<span
				class="absolute bottom-1.5 left-0 text-xs leading-none whitespace-nowrap text-muted-foreground/70"
			>
				{tick.label}
			</span>
		</span>
	{/each}
</div>

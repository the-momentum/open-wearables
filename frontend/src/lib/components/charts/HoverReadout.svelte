<script lang="ts">
	import { TOOLTIP } from '$lib/components/ui/typography';
	import { cn } from '$lib/utils/cn';

	let {
		heading,
		readings,
		at,
		colourFor,
		format
	}: {
		heading: string;
		readings: { type: string; label: string; unit: string; value: number }[];
		/** Percentage across the frame the pointer sits at. */
		at: number;
		colourFor: (type: string) => string;
		format: (value: number, unit: string) => string;
	} = $props();
</script>

<!-- Clamped inside the frame, so a reading near either end stays legible. -->
<div
	class={cn(
		'pointer-events-none absolute top-1 z-10 flex -translate-x-1/2 flex-col gap-0.5',
		TOOLTIP
	)}
	style="left: clamp(4rem, {at}%, calc(100% - 4rem))"
>
	<span class="font-medium tabular-nums">{heading}</span>
	{#each readings as reading (reading.label)}
		<span class="flex items-center gap-1.5 whitespace-nowrap tabular-nums opacity-80">
			<span
				aria-hidden="true"
				class="size-2 rounded-full"
				style="background: {colourFor(reading.type)}"
			></span>
			{format(reading.value, reading.unit)}
		</span>
	{/each}
</div>

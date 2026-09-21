<script lang="ts">
	import { seriesColour, unitLabel } from '$lib/timeseries/samples';
	import { formatNumber } from '$lib/utils/format';

	let {
		heading,
		readings,
		at
	}: {
		heading: string;
		readings: { type: string; label: string; unit: string; value: number }[];
		/** Percentage across the frame the pointer sits at. */
		at: number;
	} = $props();
</script>

<!-- Clamped inside the frame, so a reading near either end stays legible. -->
<div
	class="pointer-events-none absolute top-1 flex -translate-x-1/2 flex-col gap-0.5 rounded-lg
		border border-border bg-surface px-2 py-1.5 text-[11px] shadow-sm"
	style="left: clamp(4rem, {at}%, calc(100% - 4rem))"
>
	<span class="font-medium text-foreground tabular-nums">{heading}</span>
	{#each readings as reading (reading.label)}
		<span class="flex items-center gap-1.5 whitespace-nowrap text-muted-foreground">
			<span
				aria-hidden="true"
				class="size-1.5 rounded-full"
				style="background: {seriesColour(reading.type)}"
			></span>
			{formatNumber(reading.value, unitLabel(reading.unit))}
		</span>
	{/each}
</div>

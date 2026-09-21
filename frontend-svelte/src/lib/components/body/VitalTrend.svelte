<script lang="ts">
	import type { Component } from 'svelte';
	import { extent } from '$lib/charts/geometry';
	import Sparkline from '$lib/components/charts/Sparkline.svelte';
	import Caption from '$lib/components/ui/Caption.svelte';
	import { MICRO } from '$lib/components/ui/typography';
	import { seriesColour, unitLabel, type Series } from '$lib/timeseries/samples';
	import { showDecimal } from '$lib/utils/format';

	let {
		series,
		label,
		icon,
		digits,
		from,
		to
	}: {
		series: Series;
		label: string;
		icon?: Component;
		digits: number;
		from: number;
		to: number;
	} = $props();

	const range = $derived(extent(series.points));
	const latest = $derived(series.points[series.points.length - 1]);

	const show = (value: number) => showDecimal(value, digits);
	const colour = $derived(seriesColour(series.type));
</script>

<div class="flex flex-col gap-2 rounded-xl border border-border bg-surface p-4">
	<div class="flex items-baseline justify-between gap-3">
		<Caption {icon}>{label}</Caption>
		<span class="text-lg font-semibold tabular-nums" style="color: {colour}">
			{show(latest.value)}<span class="text-xs font-normal text-muted-foreground">
				{unitLabel(series.unit)}
			</span>
		</span>
	</div>

	<!-- Its own scale, because a pulse and a percentage share no axis. -->
	<Sparkline lines={[series]} {range} {from} {to} colourFor={() => colour} />

	<div class="flex justify-between {MICRO} tabular-nums">
		<span>low {show(range.low)}</span>
		<span>{series.points.length} days</span>
		<span>high {show(range.high)}</span>
	</div>
</div>

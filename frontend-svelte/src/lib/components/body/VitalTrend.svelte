<script lang="ts">
	import type { Component } from 'svelte';
	import { extent, linePath } from '$lib/charts/geometry';
	import Caption from '$lib/components/ui/Caption.svelte';
	import { MICRO } from '$lib/components/ui/typography';
	import { seriesColour, unitLabel, type Series } from '$lib/timeseries/samples';
	import { formatDecimal } from '$lib/utils/format';

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

	const BOX = { width: 400, height: 90, pad: 8 };

	const range = $derived(extent(series.points));
	const latest = $derived(series.points[series.points.length - 1]);
	const path = $derived(linePath(series.points, { from, to }, range, BOX));

	const show = (value: number) => formatDecimal(value, digits);
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

	<!-- One point a day, so a month is thirty of them and the shape is the point.
	     Its own scale, because a pulse and a percentage share no axis. -->
	<svg
		viewBox="0 0 {BOX.width} {BOX.height}"
		preserveAspectRatio="none"
		class="h-16 w-full"
		aria-hidden="true"
	>
		<path
			d={path}
			fill="none"
			stroke={colour}
			stroke-width="1.75"
			stroke-linejoin="round"
			vector-effect="non-scaling-stroke"
		/>
	</svg>

	<div class="flex justify-between {MICRO} tabular-nums">
		<span>low {show(range.low)}</span>
		<span>{series.points.length} days</span>
		<span>high {show(range.high)}</span>
	</div>
</div>

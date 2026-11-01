<script lang="ts">
	import HoverReadout from '$lib/components/charts/HoverReadout.svelte';
	import { MICRO } from '$lib/components/ui/typography';
	import { CHART_BOX, linePath } from '$lib/charts/geometry';
	import { DAYS_PER_MONTH, PROJECTION_MONTHS } from '$lib/lifecycle/projection';
	import { formatBytes } from '$lib/utils/format';

	let { points, colour }: { points: { month: number; bytes: number }[]; colour: string } = $props();

	const { width: W, height: H } = CHART_BOX;
	const window = { from: 0, to: PROJECTION_MONTHS };

	// From zero, not from the lowest point: the question is how big it gets, and
	// a trimmed axis makes a capped total look like it is still climbing.
	const range = $derived({
		low: 0,
		high: Math.max(...points.map((point) => point.bytes), 1) * 1.08
	});
	const line = $derived(
		linePath(
			points.map((point) => ({ at: point.month, value: point.bytes })),
			window,
			range,
			CHART_BOX
		)
	);
	const area = $derived(`${line} L${W} ${H} L0 ${H} Z`);

	let hovered = $state<number | null>(null);

	function track(event: PointerEvent) {
		const box = (event.currentTarget as HTMLElement).getBoundingClientRect();
		const share = Math.min(Math.max((event.clientX - box.left) / box.width, 0), 1);
		hovered = Math.round(share * PROJECTION_MONTHS);
	}

	const TICKS = [0, 6, 12, 18];
	const tickLabel = (month: number) => (month === 0 ? 'Today' : `${month} mo`);
</script>

<div class="flex flex-col gap-1.5">
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div class="relative h-44" onpointermove={track} onpointerleave={() => (hovered = null)}>
		<svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" class="size-full" aria-hidden="true">
			{#each [0.25, 0.5, 0.75] as fraction (fraction)}
				<line
					x1="0"
					x2={W}
					y1={H * fraction}
					y2={H * fraction}
					class="stroke-border"
					stroke-dasharray="4 4"
					vector-effect="non-scaling-stroke"
				/>
			{/each}
			<path d={area} fill={colour} fill-opacity="0.12" />
			<path
				d={line}
				fill="none"
				stroke={colour}
				stroke-width="2"
				stroke-linejoin="round"
				vector-effect="non-scaling-stroke"
			/>
			{#if hovered !== null}
				<line
					x1={(hovered / PROJECTION_MONTHS) * W}
					x2={(hovered / PROJECTION_MONTHS) * W}
					y1="0"
					y2={H}
					class="stroke-muted-foreground/40"
					vector-effect="non-scaling-stroke"
				/>
			{/if}
		</svg>

		<span class="pointer-events-none absolute top-0 left-1 {MICRO}">{formatBytes(range.high)}</span>

		{#if hovered !== null}
			<HoverReadout
				heading={hovered === 0 ? 'Today' : `In ${hovered} months (day ${hovered * DAYS_PER_MONTH})`}
				readings={[
					{ type: 'size', label: 'Estimated size', unit: '', value: points[hovered].bytes }
				]}
				at={(hovered / PROJECTION_MONTHS) * 100}
				colourFor={() => colour}
				format={(value) => formatBytes(value)}
			/>
		{/if}
	</div>

	<div class="flex justify-between tabular-nums {MICRO}">
		{#each TICKS as month (month)}
			<span>{tickLabel(month)}</span>
		{/each}
	</div>
</div>

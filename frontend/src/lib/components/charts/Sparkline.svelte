<script lang="ts">
	import { linePath, SPARK_BOX, type Line } from '$lib/charts/geometry';

	let {
		lines,
		range,
		from,
		to,
		colourFor
	}: {
		lines: Line[];
		/** Shared by every line, so two of them can be compared by height. */
		range: { low: number; high: number };
		from: number;
		to: number;
		colourFor: (type: string) => string;
	} = $props();
</script>

<!-- A point a day, so a month is thirty of them and the shape is the whole
     point: no axis, no hover, no grid. The figures around it carry the numbers. -->
<svg
	viewBox="0 0 {SPARK_BOX.width} {SPARK_BOX.height}"
	preserveAspectRatio="none"
	class="h-16 w-full"
	aria-hidden="true"
>
	{#each lines as line (line.label)}
		<path
			d={linePath(line.points, { from, to }, range, SPARK_BOX)}
			fill="none"
			stroke={colourFor(line.type)}
			stroke-width="1.75"
			stroke-linejoin="round"
			vector-effect="non-scaling-stroke"
		/>
	{/each}
</svg>

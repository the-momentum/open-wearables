<svelte:options namespace="svg" />

<script lang="ts">
	import type { Box } from '$lib/charts/geometry';

	let { box }: { box: Pick<Box, 'width' | 'height'> } = $props();
</script>

<!-- Quarters of the frame, dashed in the line colour: a guide to read heights
     against, never a scale - each line may be drawn on its own. -->
<g aria-hidden="true">
	{#each [0.25, 0.5, 0.75] as fraction (fraction)}
		<line
			x1="0"
			x2={box.width}
			y1={box.height * fraction}
			y2={box.height * fraction}
			class="stroke-border"
			stroke-dasharray="4 4"
			vector-effect="non-scaling-stroke"
		/>
	{/each}
</g>

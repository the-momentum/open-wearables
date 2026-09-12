<script lang="ts">
	import ChartRow from '$lib/components/ui/ChartRow.svelte';
	import { heatShade } from '$lib/summary/shades';
	import type { Row } from '$lib/summary/timeline';

	let { row, label, max, unit }: { row: Row; label: string; max: number; unit: string } = $props();
</script>

<ChartRow {label} value={row.total} hoverable>
	<!-- Contiguous, not gapped: 90 columns of 2px gaps come to 178px, most of a
	     phone. Cells flex, so the strip fits any width and the ramp separates them. -->
	<div
		class="flex h-5 overflow-hidden rounded-[3px] ring-primary/30 transition-shadow
			group-hover:ring-1"
	>
		{#each row.cells as cell (cell.date)}
			<span class="flex-1 {heatShade(cell.count, max)}" title="{unit}{cell.date} · {cell.count}"
			></span>
		{/each}
	</div>
</ChartRow>

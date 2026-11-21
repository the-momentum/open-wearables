<script lang="ts">
	import LegendItem from '$lib/components/charts/LegendItem.svelte';
	import { phaseLabel, phaseShade, PHASE_ORDER } from '$lib/cycles/phases';
</script>

<!-- One legend for the whole list: the bars are the same four colours all the
     way down, and a key inside each card would be the same key fifteen times. -->
<div class="flex flex-wrap items-center gap-x-4 gap-y-1.5">
	{#each PHASE_ORDER as phase (phase)}
		<LegendItem label={phaseLabel(phase) ?? phase} shade={phaseShade(phase)} />
	{/each}
</div>

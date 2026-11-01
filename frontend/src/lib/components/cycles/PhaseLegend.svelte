<script lang="ts">
	import { MICRO } from '$lib/components/ui/typography';
	import { phaseLabel, phaseShade, PHASE_ORDER } from '$lib/cycles/phases';
</script>

<!-- One legend for the whole list: the bars are the same four colours all the
     way down, and a key inside each card would be the same key fifteen times. -->
<div class="flex flex-wrap items-center gap-x-4 gap-y-1.5 {MICRO}">
	{#each PHASE_ORDER as phase (phase)}
		<span class="flex items-center gap-1.5">
			<span aria-hidden="true" class="size-2 rounded-[2px] {phaseShade(phase)}"></span>
			{phaseLabel(phase)}
		</span>
	{/each}
</div>

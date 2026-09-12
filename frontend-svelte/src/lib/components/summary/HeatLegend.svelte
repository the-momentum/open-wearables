<script lang="ts">
	import { CELL_SHAPE, HEAT_STEPS } from '$lib/summary/shades';

	let { peak }: { peak: number } = $props();
</script>

<div class="flex items-center gap-1.5 text-[11px] text-muted-foreground">
	<span>Less</span>
	{#each HEAT_STEPS as step (step)}
		<span aria-hidden="true" class="{CELL_SHAPE} {step}"></span>
	{/each}
	<span>More</span>
	<span class="ml-2 tabular-nums">peak {peak}</span>
</div>

<script lang="ts">
	import { windowOf } from '$lib/charts/geometry';
	import LineChart from '$lib/components/charts/LineChart.svelte';
	import Caption from '$lib/components/ui/Caption.svelte';
	import FieldGroups from '$lib/components/ui/FieldGroups.svelte';
	import { categorySpec } from '$lib/scores/categories';
	import type { DetailSection } from '$lib/scores/details';
	import { formatLocalTime, showDecimal } from '$lib/utils/format';

	let {
		section,
		zoneOffset,
		colourFor
	}: {
		section: DetailSection;
		zoneOffset: string | null;
		colourFor: (provider: string) => string;
	} = $props();

	const spec = $derived(categorySpec(section.category));
	const window = $derived(windowOf(section.lines));
</script>

<div class="flex flex-col gap-3">
	<Caption icon={spec.icon}>{spec.label}</Caption>

	{#if section.lines.length > 0}
		<LineChart
			series={section.lines}
			zones={null}
			from={window.from}
			to={window.to}
			{colourFor}
			format={(value) => showDecimal(value)}
			shared
			formatTime={(at) => formatLocalTime(new Date(at).toISOString(), zoneOffset)}
			label="{spec.label} readings across the day"
		/>
	{/if}

	<FieldGroups groups={section.groups} />
</div>

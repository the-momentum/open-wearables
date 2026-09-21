<script lang="ts">
	import { VITALS } from '$lib/body/metrics';
	import Skeleton from '$lib/components/ui/Skeleton.svelte';
	import { NOTE } from '$lib/components/ui/typography';
	import { dailyMeans, toSeries, VITAL_TYPES, type Sample } from '$lib/timeseries/samples';
	import { resource } from '$lib/utils/resource.svelte';
	import VitalTrend from './VitalTrend.svelte';

	let { url, from, to }: { url: () => string; from: number; to: number } = $props();

	const fetched = resource<{ samples: Sample[]; truncated: boolean }>(() => url());

	// Averaged to one point a day: HRV alone arrives dozens of times a day, and a
	// body trend is read by the day. A series from two devices stays two lines.
	const trends = $derived(
		toSeries(fetched.current?.samples ?? [], VITAL_TYPES)
			.map(dailyMeans)
			// One point draws no line, and a flat dot says less than the figure above.
			.filter((series) => series.points.length > 1)
	);
</script>

{#if !fetched.settled}
	<div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
		{#each [1, 2, 3] as key (key)}
			<Skeleton class="h-40" />
		{/each}
	</div>
{:else if trends.length === 0}
	<p class={NOTE}>No vital was recorded on more than one day in this period.</p>
{:else}
	<div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
		{#each trends as series (series.label)}
			{@const vital = VITALS[series.type]}
			<VitalTrend
				{series}
				label={vital?.label ?? series.label}
				icon={vital?.icon}
				digits={vital?.digits ?? 1}
				{from}
				{to}
			/>
		{/each}
	</div>
{/if}

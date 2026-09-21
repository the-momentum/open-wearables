<script lang="ts">
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import Caption from '$lib/components/ui/Caption.svelte';
	import FieldGroups from '$lib/components/ui/FieldGroups.svelte';
	import Segmented from '$lib/components/ui/Segmented.svelte';
	import Skeleton from '$lib/components/ui/Skeleton.svelte';
	import { MICRO, NOTE } from '$lib/components/ui/typography';
	import { formatLocalTime } from '$lib/utils/format';
	import { resource } from '$lib/utils/resource.svelte';
	import { detailGroups } from '$lib/workouts/fields';
	import { toSeries, type Sample } from '$lib/timeseries/samples';
	import type { Workout } from '$lib/workouts/types';
	import { zoneKinds, zoneRows } from '$lib/workouts/zones';
	import DistributionBar from '$lib/components/charts/DistributionBar.svelte';
	import LineChart from '$lib/components/charts/LineChart.svelte';

	let { workout, userId, ondelete }: { workout: Workout; userId: string; ondelete: () => void } =
		$props();

	const from = $derived(new Date(workout.start_time).getTime());
	const to = $derived(new Date(workout.end_time).getTime());

	// One set of zones at a time, chosen once for both the bands and the strip:
	// two strips side by side left the bands unattributed, which is the question
	// the chart could not answer.
	const kinds = $derived(zoneKinds(workout));
	let chosen = $state('');
	const kind = $derived(kinds.find((entry) => entry.type === chosen) ?? kinds[0]);

	// The card only mounts this when it opens, so the fetch is the expansion: ten
	// workouts' worth of curves would be ten timeseries scans for the nine nobody
	// looks at.
	const samples = resource<{ samples: Sample[]; truncated: boolean; resolution: string }>(() => {
		const params = new URLSearchParams({
			from: workout.start_time,
			to: workout.end_time,
			seconds: String(Math.round((to - from) / 1000)),
			provider: workout.source.provider
		});
		return `/users/${userId}/workouts/samples?${params}`;
	});

	const series = $derived(toSeries(samples.current?.samples ?? []));
	const bucket = $derived(
		samples.current && samples.current.resolution !== 'raw' ? samples.current : null
	);
</script>

<div class="flex flex-col gap-5 border-t border-border pt-4">
	<div class="flex flex-col gap-1.5">
		<Caption>During the workout</Caption>

		{#if !samples.settled}
			<Skeleton class="h-44" />
		{:else if series.length === 0}
			<p class={NOTE}>No readings were stored inside this workout's window.</p>
		{:else}
			<LineChart
				{series}
				zones={kind}
				{from}
				{to}
				formatTime={(at) => formatLocalTime(new Date(at).toISOString(), workout.zone_offset)}
				label="Sensor readings across the workout"
			/>

			{#if bucket}
				<!-- Say which, because an average is a different curve: the peaks a
				     phone shows are exactly what a bucket flattens. -->
				<p class={MICRO}>
					Too many readings to plot one by one, so these are averages per {bucket.resolution.replace(
						'min',
						' minute'
					)}{bucket.truncated ? ', and still more than one page holds' : ''}.
				</p>
			{/if}
		{/if}
	</div>

	{#if kind}
		<DistributionBar
			title="Time in {kind.label.toLowerCase()} zones"
			icon={kind.icon}
			unit={kind.unit}
			rows={zoneRows(kind)}
		>
			{#if kinds.length > 1}
				<Segmented
					label="Zones"
					items={kinds.map((entry) => ({ value: entry.type, label: entry.label }))}
					selected={kind.type}
					onselect={(value) => (chosen = value)}
				/>
			{/if}
		</DistributionBar>
	{/if}

	<FieldGroups groups={detailGroups(workout)} />

	<div class="flex items-center justify-between gap-3 border-t border-border pt-3">
		<!-- Laps are stored but not drawn yet; saying so beats an empty space that
		     reads as "this workout has none". -->
		<span class="text-xs text-muted-foreground">
			{workout.segments?.length ? `${workout.segments.length} laps recorded` : ''}
		</span>

		<button
			type="button"
			onclick={ondelete}
			class="inline-flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-danger"
		>
			<Trash2 size={14} aria-hidden="true" />
			Delete workout
		</button>
	</div>
</div>

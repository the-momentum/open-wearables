<script lang="ts">
	import DeleteAction from '$lib/components/events/DeleteAction.svelte';
	import Caption from '$lib/components/ui/Caption.svelte';
	import FieldGroups from '$lib/components/ui/FieldGroups.svelte';
	import Segmented from '$lib/components/ui/Segmented.svelte';
	import { formatLocalTime } from '$lib/utils/format';
	import { detailGroups } from '$lib/workouts/fields';
	import { WORKOUT_TYPES } from '$lib/timeseries/samples';
	import type { Workout } from '$lib/workouts/types';
	import { zoneKinds, zoneRows } from '$lib/workouts/zones';
	import DistributionBar from '$lib/components/charts/DistributionBar.svelte';
	import SamplesChart from '$lib/components/charts/SamplesChart.svelte';

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

	const params = $derived(
		new URLSearchParams({
			from: workout.start_time,
			to: workout.end_time,
			seconds: String(Math.round((to - from) / 1000)),
			provider: workout.source.provider
		})
	);
</script>

<div class="flex flex-col gap-5 border-t border-border pt-4">
	<div class="flex flex-col gap-1.5">
		<Caption>During the workout</Caption>

		<SamplesChart
			url={() => `/users/${userId}/workouts/samples?${params}`}
			order={WORKOUT_TYPES}
			zones={kind}
			{from}
			{to}
			formatTime={(at) => formatLocalTime(new Date(at).toISOString(), workout.zone_offset)}
			label="Sensor readings across the workout"
			empty="No readings were stored inside this workout's window."
		/>
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

		<DeleteAction label="Delete workout" onclick={ondelete} />
	</div>
</div>

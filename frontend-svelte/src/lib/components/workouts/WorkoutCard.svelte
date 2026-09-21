<script lang="ts">
	import EventCard from '$lib/components/events/EventCard.svelte';
	import TimeRange from '$lib/components/ui/TimeRange.svelte';
	import { HEADING } from '$lib/components/ui/typography';
	import { humanise } from '$lib/utils/text';
	import { workoutIcon } from '$lib/workouts/kinds';
	import type { Workout } from '$lib/workouts/types';
	import WorkoutDetails from './WorkoutDetails.svelte';
	import WorkoutMetrics from './WorkoutMetrics.svelte';

	let {
		workout,
		providerLabel,
		userId,
		ondelete
	}: { workout: Workout; providerLabel: string; userId: string; ondelete: () => void } = $props();
</script>

<EventCard icon={workoutIcon(workout.type)} source={workout.source} {providerLabel}>
	{#snippet title()}
		<span class="flex flex-wrap items-baseline gap-x-2">
			<span class={HEADING}>{humanise(workout.type)}</span>
			{#if workout.name}
				<span class="truncate text-xs text-muted-foreground">{workout.name}</span>
			{/if}
		</span>
	{/snippet}

	{#snippet when()}
		<!-- Dated by its start: a workout happened on the evening it began, so the
		     weekday rides on the end instead. -->
		<TimeRange from={workout.start_time} to={workout.end_time} zoneOffset={workout.zone_offset} />
	{/snippet}

	{#snippet metrics()}
		<WorkoutMetrics {workout} />
	{/snippet}

	{#snippet details()}
		<WorkoutDetails {workout} {userId} {ondelete} />
	{/snippet}
</EventCard>

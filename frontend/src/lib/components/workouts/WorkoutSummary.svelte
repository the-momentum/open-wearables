<script lang="ts">
	import Dumbbell from '@lucide/svelte/icons/dumbbell';
	import Flame from '@lucide/svelte/icons/flame';
	import Route from '@lucide/svelte/icons/route';
	import Timer from '@lucide/svelte/icons/timer';
	import EventTotals from '$lib/components/events/EventTotals.svelte';
	import { DASH, formatDistance, formatDuration, formatNumber } from '$lib/utils/format';
	import type { WorkoutTotals } from '$lib/workouts/totals';

	let { userId, search }: { userId: string; search: string } = $props();
</script>

<EventTotals
	url={() => `/users/${userId}/workouts/totals${search}`}
	label="Workout totals"
	noun="workouts"
	figures={(totals: WorkoutTotals) => [
		{ icon: Dumbbell, label: 'Workouts', value: totals.count },
		{ icon: Timer, label: 'Total time', value: formatDuration(totals.seconds) },
		{
			icon: Flame,
			label: 'Calories',
			value: totals.calories > 0 ? formatNumber(totals.calories) : DASH
		},
		{ icon: Route, label: 'Distance', value: formatDistance(totals.meters) }
	]}
/>

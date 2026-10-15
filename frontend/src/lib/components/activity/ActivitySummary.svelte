<script lang="ts">
	import CalendarDays from '@lucide/svelte/icons/calendar-days';
	import Footprints from '@lucide/svelte/icons/footprints';
	import Route from '@lucide/svelte/icons/route';
	import type { ActivityTotals } from '$lib/activity/totals';
	import EventTotals from '$lib/components/events/EventTotals.svelte';
	import { DASH, formatDistance, formatNumber } from '$lib/utils/format';

	let { userId, search }: { userId: string; search: string } = $props();
</script>

<EventTotals
	url={() => `/users/${userId}/activity/totals${search}`}
	label="Activity totals"
	noun="days"
	figures={(totals: ActivityTotals) => [
		{ icon: CalendarDays, label: 'Days with data', value: totals.count },
		{ icon: Footprints, label: 'Total steps', value: formatNumber(totals.steps) },
		{
			icon: Footprints,
			label: 'Avg steps a day',
			value: totals.averageSteps === null ? DASH : formatNumber(totals.averageSteps)
		},
		{ icon: Route, label: 'Distance', value: formatDistance(totals.meters) }
	]}
/>

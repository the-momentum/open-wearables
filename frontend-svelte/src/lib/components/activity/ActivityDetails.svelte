<script lang="ts">
	import Activity from '@lucide/svelte/icons/activity';
	import { detailGroups } from '$lib/activity/fields';
	import type { ActivityDay } from '$lib/activity/types';
	import SamplesChart from '$lib/components/charts/SamplesChart.svelte';
	import Caption from '$lib/components/ui/Caption.svelte';
	import FieldGroups from '$lib/components/ui/FieldGroups.svelte';
	import { ACTIVITY_TYPES } from '$lib/timeseries/samples';
	import { formatLocalTime } from '$lib/utils/format';

	let { day, userId }: { day: ActivityDay; userId: string } = $props();

	// A calendar date with no offset in the response, so the window is that date's
	// UTC midnights — which is not quite the local day the sums were taken over.
	const from = $derived(`${day.date}T00:00:00Z`);
	const to = $derived(`${day.date}T23:59:59Z`);

	const params = $derived(
		new URLSearchParams({ from, to, seconds: '86400', provider: day.source.provider })
	);
</script>

<div class="flex flex-col gap-5 border-t border-border pt-4">
	<div class="flex flex-col gap-1.5">
		<Caption icon={Activity}>Through the day</Caption>

		<SamplesChart
			url={() => `/users/${userId}/activity/samples?${params}`}
			order={ACTIVITY_TYPES}
			from={new Date(from).getTime()}
			to={new Date(to).getTime()}
			formatTime={(at) => formatLocalTime(new Date(at).toISOString(), null)}
			label="Readings across the day"
			empty="No readings were stored for this day."
		/>
	</div>

	<FieldGroups groups={detailGroups(day)} />
</div>

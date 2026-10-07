<script lang="ts">
	import Activity from '@lucide/svelte/icons/activity';
	import EventCard from '$lib/components/events/EventCard.svelte';
	import { HEADING, MICRO } from '$lib/components/ui/typography';
	import type { ActivityDay } from '$lib/activity/types';
	import { formatDate } from '$lib/utils/datetime';
	import ActivityDetails from './ActivityDetails.svelte';
	import ActivityMetrics from './ActivityMetrics.svelte';

	let { day, providerLabel, userId }: { day: ActivityDay; providerLabel: string; userId: string } =
		$props();

	// A weekday tells an admin more than the date alone: "no steps on Sundays" is
	// a pattern, "no steps on the 14th" is not.
	const weekday = new Intl.DateTimeFormat('en-GB', { weekday: 'long', timeZone: 'UTC' });
	const named = $derived(weekday.format(new Date(`${day.date}T00:00:00Z`)));
</script>

<EventCard icon={Activity} source={day.source} {providerLabel}>
	{#snippet title()}
		<span class={HEADING}>{named}</span>
	{/snippet}

	{#snippet when()}
		<!-- A day, not a range: this row is an aggregate of one calendar date. -->
		<span class={MICRO}>{formatDate(`${day.date}T00:00:00Z`)}</span>
	{/snippet}

	{#snippet metrics()}
		<ActivityMetrics {day} />
	{/snippet}

	{#snippet details()}
		<ActivityDetails {day} {userId} />
	{/snippet}
</EventCard>

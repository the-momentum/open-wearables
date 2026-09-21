<script lang="ts">
	import BedDouble from '@lucide/svelte/icons/bed-double';
	import Sunrise from '@lucide/svelte/icons/sunrise';
	import EventCard from '$lib/components/events/EventCard.svelte';
	import TimeRange from '$lib/components/ui/TimeRange.svelte';
	import { sleepIcon, sleepKind } from '$lib/sleep/session';
	import type { SleepSession } from '$lib/sleep/types';
	import SleepDetails from './SleepDetails.svelte';
	import SleepMetrics from './SleepMetrics.svelte';

	let {
		session,
		providerLabel,
		ondelete
	}: { session: SleepSession; providerLabel: string; ondelete: () => void } = $props();
</script>

<EventCard icon={sleepIcon(session)} source={session.source} {providerLabel}>
	{#snippet title()}
		<span class="text-sm font-semibold text-foreground">{sleepKind(session)}</span>
	{/snippet}

	{#snippet when()}
		<!-- Dated by when it ended: a night belongs to the morning someone woke up
		     in, so the weekday rides on the bedtime instead. -->
		<TimeRange
			from={session.start_time}
			to={session.end_time}
			zoneOffset={session.zone_offset}
			fromIcon={BedDouble}
			toIcon={Sunrise}
			dateBy="to"
		/>
	{/snippet}

	{#snippet metrics()}
		<SleepMetrics {session} />
	{/snippet}

	{#snippet details()}
		<SleepDetails {session} {ondelete} />
	{/snippet}
</EventCard>

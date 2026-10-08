<script lang="ts">
	import CalendarClock from '@lucide/svelte/icons/calendar-clock';
	import Heart from '@lucide/svelte/icons/heart';
	import SpanBar from '$lib/components/charts/SpanBar.svelte';
	import EventCard from '$lib/components/events/EventCard.svelte';
	import Badge from '$lib/components/ui/Badge.svelte';
	import { HEADING, MICRO } from '$lib/components/ui/typography';
	import { currentDay, cycleDays, phaseLabel, phaseSpans } from '$lib/cycles/phases';
	import type { Cycle } from '$lib/cycles/types';
	import { formatDays, formatLocalDate } from '$lib/utils/format';
	import CycleDetails from './CycleDetails.svelte';

	let {
		cycle,
		days,
		providerLabel,
		ondelete
	}: {
		cycle: Cycle;
		/** The longest cycle on the page, so every bar is drawn to one scale. */
		days: number;
		providerLabel: string;
		ondelete: () => void;
	} = $props();

	const today = $derived(currentDay(cycle));
	const phase = $derived(phaseLabel(cycle.current_phase_type));
	const length = $derived(cycleDays(cycle));

	const spans = $derived(
		phaseSpans(cycle).map((span) => ({
			...span,
			title: `${span.label}: day ${span.from}–${span.to}`
		}))
	);
</script>

<EventCard
	icon={cycle.is_predicted_cycle ? CalendarClock : Heart}
	source={cycle.source}
	{providerLabel}
>
	{#snippet title()}
		<!-- The dates identify the cycle; the phase below is only where the
		     provider's last snapshot caught it. -->
		<span class={HEADING}>
			{formatLocalDate(cycle.start_time, cycle.zone_offset)} – {formatLocalDate(
				cycle.end_time,
				cycle.zone_offset
			)}
		</span>
	{/snippet}

	{#snippet when()}
		<span class="flex flex-wrap items-center gap-2 {MICRO}">
			{#if cycle.is_predicted_cycle}
				<Badge>Predicted</Badge>
			{:else if phase}
				<span>{phase}</span>
			{/if}
			{#if today !== null}
				<span aria-hidden="true" class="text-muted-foreground/40">·</span>
				<span>Day {today} today</span>
			{/if}
		</span>
	{/snippet}

	{#snippet metrics()}
		{#if length}
			<div class="flex items-center gap-3">
				<SpanBar
					{spans}
					to={days}
					marker={today === null ? null : { at: today, title: `Day ${today}` }}
				/>
				<!-- The cycle's own length, not the end of the last span: without a
				     fertile window the bar stops after the period, and the cycle does not. -->
				<span class="w-14 shrink-0 text-right tabular-nums {MICRO}">{formatDays(length)}</span>
			</div>
		{/if}
	{/snippet}

	{#snippet details()}
		<CycleDetails {cycle} {ondelete} />
	{/snippet}
</EventCard>

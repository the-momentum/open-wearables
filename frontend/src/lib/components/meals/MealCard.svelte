<script lang="ts">
	import Utensils from '@lucide/svelte/icons/utensils';
	import EventCard from '$lib/components/events/EventCard.svelte';
	import { HEADING, MICRO } from '$lib/components/ui/typography';
	import { mealTitle, mealTypeLabel } from '$lib/meals/meal';
	import type { Meal } from '$lib/meals/types';
	import { formatLocalDay, formatLocalTime } from '$lib/utils/format';
	import MealDetails from './MealDetails.svelte';
	import MealMetrics from './MealMetrics.svelte';

	let {
		meal,
		providerLabel,
		ondelete
	}: { meal: Meal; providerLabel: string; ondelete: () => void } = $props();

	// The type is the title when there is no name, so it is repeated only beside one.
	const type = $derived(meal.name ? mealTypeLabel(meal.meal_type) : null);
</script>

<EventCard icon={Utensils} source={meal.source} {providerLabel}>
	{#snippet title()}
		<span class={HEADING}>{mealTitle(meal)}</span>
	{/snippet}

	{#snippet when()}
		<!-- The record card's time row: the date muted, the clock time not. -->
		<span class="flex flex-wrap items-center gap-x-2 {MICRO}">
			<span>{formatLocalDay(meal.timestamp, null)}</span>
			<span class="text-secondary-foreground tabular-nums">
				{formatLocalTime(meal.timestamp, null)}
			</span>
			{#if type}<span>· {type}</span>{/if}
		</span>
	{/snippet}

	{#snippet metrics()}
		<MealMetrics {meal} />
	{/snippet}

	{#snippet details()}
		<MealDetails {meal} {ondelete} />
	{/snippet}
</EventCard>

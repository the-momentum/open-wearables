<script lang="ts">
	import Beef from '@lucide/svelte/icons/beef';
	import CalendarDays from '@lucide/svelte/icons/calendar-days';
	import Flame from '@lucide/svelte/icons/flame';
	import Utensils from '@lucide/svelte/icons/utensils';
	import EventTotals from '$lib/components/events/EventTotals.svelte';
	import type { MealTotals } from '$lib/meals/totals';
	import { formatNumber } from '$lib/utils/format';

	let { userId, search }: { userId: string; search: string } = $props();
</script>

<EventTotals
	url={() => `/users/${userId}/meals/totals${search}`}
	label="Meal totals"
	noun="meals"
	figures={(totals: MealTotals) => [
		{ icon: Utensils, label: 'Meals', value: totals.count },
		{ icon: Flame, label: 'Calories', value: formatNumber(totals.calories, ' kcal') },
		{
			icon: CalendarDays,
			label: 'Per day logged',
			value: formatNumber(totals.caloriesPerDay, ' kcal')
		},
		{ icon: Beef, label: 'Protein', value: formatNumber(totals.protein, ' g') }
	]}
/>

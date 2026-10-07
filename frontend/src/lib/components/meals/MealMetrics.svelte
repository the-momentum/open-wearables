<script lang="ts">
	import Beef from '@lucide/svelte/icons/beef';
	import Droplet from '@lucide/svelte/icons/droplet';
	import Flame from '@lucide/svelte/icons/flame';
	import Wheat from '@lucide/svelte/icons/wheat';
	import MetricRow from '$lib/components/events/MetricRow.svelte';
	import type { Meal } from '$lib/meals/types';
	import { formatAmount } from '$lib/meals/nutrients';
	import { formatNumber } from '$lib/utils/format';

	let { meal }: { meal: Meal } = $props();

	const metrics = $derived([
		{ icon: Flame, label: 'Calories', value: formatNumber(meal.calories_kcal, ' kcal') },
		{ icon: Beef, label: 'Protein', value: formatAmount(meal.macros?.protein_g, 'g') },
		{ icon: Wheat, label: 'Carbs', value: formatAmount(meal.macros?.carbohydrates_g, 'g') },
		{ icon: Droplet, label: 'Fat', value: formatAmount(meal.macros?.fat_g, 'g') }
	]);
</script>

<MetricRow {metrics} />

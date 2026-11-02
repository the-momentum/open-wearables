<script lang="ts">
	import Utensils from '@lucide/svelte/icons/utensils';
	import SectionCard from './SectionCard.svelte';
	import NumberField from '$lib/components/ui/NumberField.svelte';
	import RangeField from '$lib/components/ui/RangeField.svelte';
	import { MICRO } from '$lib/components/ui/typography';
	import { LIMITS, type Draft } from '$lib/seed/draft';
	import { mealSummary } from '$lib/seed/summary';

	let { meals = $bindable() }: { meals: Draft['meals'] } = $props();
</script>

<SectionCard icon={Utensils} title="Meals" summary={mealSummary(meals)} bind:on={meals.on}>
	<div class="flex flex-wrap gap-x-6 gap-y-4">
		<NumberField
			label="Per user"
			bind:value={meals.count}
			min={LIMITS.meals[0]}
			max={LIMITS.meals[1]}
			unit="meals"
		/>
		<RangeField
			label="Calories"
			bind:value={meals.calories}
			min={LIMITS.calories[0]}
			max={LIMITS.calories[1]}
			step={50}
			unit="kcal"
		/>
	</div>
	<!-- The backend skips meals for providers that never deliver them. -->
	<p class={MICRO}>Only Apple Health connections get meals.</p>
</SectionCard>

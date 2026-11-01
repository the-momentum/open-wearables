<script lang="ts">
	import Utensils from '@lucide/svelte/icons/utensils';
	import { page } from '$app/state';
	import FilterBar from '$lib/components/filters/FilterBar.svelte';
	import MealCard from '$lib/components/meals/MealCard.svelte';
	import MealSummary from '$lib/components/meals/MealSummary.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import CursorBar from '$lib/components/events/CursorBar.svelte';
	import DeleteEventDialog from '$lib/components/events/DeleteEventDialog.svelte';
	import { providerLabel } from '$lib/providers/labels';
	import type { Meal } from '$lib/meals/types';
	import { cursorHrefs } from '$lib/lists/cursor';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const nav = $derived(cursorHrefs(page.url));
	const { hrefFor } = $derived(nav);

	const label = (entry: string) => providerLabel(data.providers, entry);
	const connected = $derived(data.connections.map((connection) => connection.provider));

	const meals = $derived(data.meals.data);
	const filtered = $derived(Boolean(data.provider || data.period.from));

	let removing = $state<Meal | null>(null);
	let removeOpen = $state(false);
</script>

<div class="flex flex-col gap-6">
	<FilterBar
		period={data.period}
		{hrefFor}
		providers={connected}
		labelFor={label}
		selected={data.provider}
	/>

	<div class="flex flex-col gap-5 border-t border-border pt-6">
		<MealSummary userId={page.params.id ?? ''} search={page.url.search} />

		{#if meals.length === 0}
			<Card>
				<EmptyState
					icon={Utensils}
					title={filtered ? 'No meals match these filters' : 'No meals recorded'}
					description={filtered
						? 'Widen the period, or clear a filter.'
						: 'Meals arrive from food-logging apps through Apple Health, Health Connect or Google Health.'}
				/>
			</Card>
		{:else}
			<div class="flex flex-col gap-3">
				{#each meals as meal (meal.id)}
					<MealCard
						{meal}
						providerLabel={label(meal.source.provider)}
						ondelete={() => {
							removing = meal;
							removeOpen = true;
						}}
					/>
				{/each}
			</div>

			<CursorBar {nav} pagination={data.meals.pagination} size={data.pageSize} />
		{/if}
	</div>
</div>

<DeleteEventDialog
	bind:open={removeOpen}
	noun="meal"
	action="?/deleteMeal"
	field="meal"
	id={removing?.id ?? ''}
/>

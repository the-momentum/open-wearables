<script lang="ts">
	import Flame from '@lucide/svelte/icons/flame';
	import ShareBar from '$lib/components/charts/ShareBar.svelte';
	import EventDetails from '$lib/components/events/EventDetails.svelte';
	import Caption from '$lib/components/ui/Caption.svelte';
	import FieldGroups from '$lib/components/ui/FieldGroups.svelte';
	import { NOTE } from '$lib/components/ui/typography';
	import { macroEnergy, nutrientGroups } from '$lib/meals/nutrients';
	import type { Meal } from '$lib/meals/types';
	import { formatNumber } from '$lib/utils/format';

	let { meal, ondelete }: { meal: Meal; ondelete: () => void } = $props();

	const energy = $derived(macroEnergy(meal));
	const groups = $derived(nutrientGroups(meal));
</script>

<EventDetails deleteLabel="Delete meal" {ondelete}>
	{#if energy.length > 0}
		<div class="flex flex-col gap-1.5">
			<Caption icon={Flame}>Energy from macros</Caption>
			<ShareBar parts={energy} format={(part) => formatNumber(part.value, ' kcal')} />
		</div>
	{/if}

	{#if groups.length > 0}
		<FieldGroups {groups} />
	{:else}
		<p class={NOTE}>No nutrients were recorded for this meal.</p>
	{/if}
</EventDetails>

<script lang="ts">
	import { goto } from '$app/navigation';
	import FilterGroup from '$lib/components/filters/FilterGroup.svelte';
	import FilterSelect from '$lib/components/ui/FilterSelect.svelte';
	import { categoryLabel } from '$lib/scores/categories';

	let {
		category,
		categories,
		hrefFor
	}: {
		category: string;
		/** Only what the period actually holds — coverage cannot name them all. */
		categories: string[];
		hrefFor: (changes: Record<string, string | null>) => string;
	} = $props();

	const options = $derived([
		{ value: '', label: 'All categories' },
		...categories.map((entry) => ({ value: entry, label: categoryLabel(entry) }))
	]);
</script>

<!-- Nothing to choose between with one category and none chosen — but once one
     is, the control has to be there to clear it. -->
{#if categories.length > 1 || category}
	<FilterGroup label="Category">
		<FilterSelect
			label="Category"
			labelled={false}
			value={category}
			{options}
			onselect={(next) =>
				// eslint-disable-next-line svelte/no-navigation-without-resolve -- hrefFor resolves
				goto(hrefFor({ category: next || null }), { noScroll: true })}
		/>
	</FilterGroup>
{/if}

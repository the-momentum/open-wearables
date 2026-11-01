<script lang="ts">
	import type { Snippet } from 'svelte';
	import Segmented from '$lib/components/ui/Segmented.svelte';
	import type { Period } from '$lib/filters/period';
	import FilterGroup from './FilterGroup.svelte';
	import PeriodFilter from './PeriodFilter.svelte';

	let {
		period,
		hrefFor,
		providers,
		labelFor,
		selected,
		periodLabel = 'Period',
		children
	}: {
		period: Period;
		hrefFor: (changes: Record<string, string | null>) => string;
		/** Provider slugs this user has connected, whatever the period holds. */
		providers: string[];
		labelFor: (provider: string) => string;
		selected: string;
		/** What the period governs, where it is not the list itself. */
		periodLabel?: string;
		/** Controls only one page needs, appended to the same row. */
		children?: Snippet;
	} = $props();

	// Links, not buttons: the server does the narrowing, so the choice has to
	// reach a load. `Segmented` marks them noscroll, which is what keeps the
	// reader in place.
	const items = $derived([
		{ value: '', label: 'All', href: hrefFor({ provider: null }) },
		...providers.map((provider) => ({
			value: provider,
			label: labelFor(provider),
			href: hrefFor({ provider })
		}))
	]);
</script>

<!-- Every filter in one place, above the cards: they govern all of them, and a
     control tucked inside one card is a control nobody finds. -->
<div class="flex flex-wrap items-end gap-x-8 gap-y-3">
	<FilterGroup label={periodLabel}><PeriodFilter {period} {hrefFor} /></FilterGroup>

	<!-- Nothing to choose between with a single connection. -->
	{#if providers.length > 1}
		<FilterGroup label="Provider">
			<Segmented label="Provider" {items} {selected} />
		</FilterGroup>
	{/if}

	{@render children?.()}
</div>

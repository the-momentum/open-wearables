<script lang="ts">
	import { goto } from '$app/navigation';
	import FilterGroup from '$lib/components/filters/FilterGroup.svelte';
	import FilterSelect from '$lib/components/ui/FilterSelect.svelte';
	import SearchField from '$lib/components/ui/SearchField.svelte';
	import Segmented from '$lib/components/ui/Segmented.svelte';
	import TabStrip from '$lib/components/ui/TabStrip.svelte';
	import { LAYERS, type Filters } from '$lib/coverage/rows';

	let {
		filters,
		providers,
		labelFor,
		hrefFor
	}: {
		filters: Filters;
		providers: string[];
		labelFor: (provider: string) => string;
		hrefFor: (changes: Record<string, string | null>) => string;
	} = $props();

	const layers = $derived([
		{ label: 'All', href: hrefFor({ layer: null }) },
		...Object.entries(LAYERS).map(([value, label]) => ({ label, href: hrefFor({ layer: value }) }))
	]);

	const providerOptions = $derived([
		{ value: '', label: 'Any provider' },
		...providers.map((provider) => ({ value: provider, label: labelFor(provider) }))
	]);

	const sides = $derived([
		{ value: 'has', label: 'Can send', href: hrefFor({ missing: null }) },
		{ value: 'missing', label: 'Cannot', href: hrefFor({ missing: '1' }) }
	]);
</script>

<div class="flex flex-wrap items-end gap-x-3 gap-y-4">
	<div class="w-full min-w-0 sm:w-auto sm:flex-1">
		<SearchField
			value={filters.search}
			hrefFor={(term) => hrefFor({ search: term || null })}
			label="Search capabilities"
			placeholder="heart_rate, vo2_max, …"
		/>
	</div>

	<FilterGroup label="Provider">
		<FilterSelect
			label="Provider"
			labelled={false}
			value={filters.provider}
			options={providerOptions}
			onselect={(provider) =>
				// eslint-disable-next-line svelte/no-navigation-without-resolve -- hrefFor resolves
				goto(hrefFor({ provider: provider || null, missing: null }), { noScroll: true })}
		/>
	</FilterGroup>

	<!-- Nothing to be missing from until a provider is chosen. -->
	{#if filters.provider}
		<FilterGroup label="Side">
			<Segmented label="Side" items={sides} selected={filters.missing ? 'missing' : 'has'} />
		</FilterGroup>
	{/if}
</div>

<!-- A filter, not a page: changing it keeps the reader where they are. -->
<div data-sveltekit-noscroll>
	<TabStrip label="Layer" tabs={layers} active={hrefFor({ layer: filters.layer || null })} />
</div>

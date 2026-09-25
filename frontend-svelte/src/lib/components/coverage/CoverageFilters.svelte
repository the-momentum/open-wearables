<script lang="ts">
	import { goto } from '$app/navigation';
	import FilterGroup from '$lib/components/filters/FilterGroup.svelte';
	import FilterSelect from '$lib/components/ui/FilterSelect.svelte';
	import ScrollFade from '$lib/components/ui/ScrollFade.svelte';
	import SearchField from '$lib/components/ui/SearchField.svelte';
	import Segmented from '$lib/components/ui/Segmented.svelte';
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
		{ value: '', label: 'All', href: hrefFor({ layer: null }) },
		...Object.entries(LAYERS).map(([value, name]) => ({
			value,
			label: name,
			href: hrefFor({ layer: value })
		}))
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

<div class="flex flex-wrap items-end gap-x-6 gap-y-3">
	<div class="min-w-56 flex-1">
		<SearchField
			value={filters.search}
			hrefFor={(term) => hrefFor({ search: term || null })}
			label="Search capabilities"
			placeholder="heart_rate, vo2_max, …"
		/>
	</div>

	<!-- `min-w-0` is what lets this shrink: a flex item keeps `min-width: auto`,
	     so without it `overflow-x-auto` has nothing to scroll inside and the whole
	     page goes sideways. `w-full` is layout — the strip gets its own row on a
	     phone rather than a sliver of one. -->
	<div class="w-full min-w-0 sm:w-auto sm:flex-1">
		<FilterGroup label="Layer">
			<ScrollFade>
				<Segmented label="Layer" items={layers} selected={filters.layer} />
			</ScrollFade>
		</FilterGroup>
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

<script lang="ts">
	import { goto } from '$app/navigation';
	import FilterGroup from '$lib/components/filters/FilterGroup.svelte';
	import FilterSelect from '$lib/components/ui/FilterSelect.svelte';
	import SearchField from '$lib/components/ui/SearchField.svelte';
	import type { Provider } from '$lib/server/providers';
	import { SYNC_STATUSES, type RunFilters } from '$lib/syncs/runs';
	import { SYNC_SOURCES, sourceLabel } from '$lib/syncs/source';
	import { humanise } from '$lib/utils/text';

	let {
		filters,
		providers,
		hrefFor
	}: {
		filters: RunFilters;
		providers: Provider[];
		hrefFor: (changes: Record<string, string | null>) => string;
	} = $props();

	const options = (label: string, values: { value: string; label: string }[]) => [
		{ value: '', label },
		...values
	];

	const providerOptions = $derived(
		options(
			'Any provider',
			providers.map((provider) => ({ value: provider.provider, label: provider.name }))
		)
	);
	const statusOptions = options(
		'Any status',
		SYNC_STATUSES.map((status) => ({ value: status, label: humanise(status) }))
	);
	const sourceOptions = options(
		'Any source',
		SYNC_SOURCES.map((source) => ({ value: source, label: sourceLabel(source) }))
	);

	const selects = $derived([
		{ key: 'provider', label: 'Provider', value: filters.provider, options: providerOptions },
		{ key: 'status', label: 'Status', value: filters.status, options: statusOptions },
		{ key: 'source', label: 'Source', value: filters.source, options: sourceOptions }
	]);

	const pick = (key: string) => (value: string) =>
		// eslint-disable-next-line svelte/no-navigation-without-resolve -- hrefFor resolves
		goto(hrefFor({ [key]: value || null }), { noScroll: true });
</script>

<div class="flex flex-wrap items-end gap-x-6 gap-y-3">
	<div class="w-full min-w-0 sm:w-72">
		<SearchField
			value={filters.user}
			hrefFor={(term) => hrefFor({ user: term || null })}
			label="User ID"
			placeholder="User ID"
		/>
	</div>

	{#each selects as select (select.key)}
		<FilterGroup label={select.label}>
			<FilterSelect
				label={select.label}
				labelled={false}
				value={select.value}
				options={select.options}
				onselect={pick(select.key)}
			/>
		</FilterGroup>
	{/each}
</div>

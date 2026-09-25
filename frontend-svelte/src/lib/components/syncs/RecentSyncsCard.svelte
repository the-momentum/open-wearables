<script lang="ts">
	import History from '@lucide/svelte/icons/history';
	import Card from '$lib/components/ui/Card.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import FilterSelect from '$lib/components/ui/FilterSelect.svelte';
	import { RECENT_SHOWN } from '$lib/syncs/recent';
	import type { SyncRunSummary } from '$lib/syncs/types';
	import { shallowParam } from '$lib/utils/shallow.svelte';
	import SyncRunRow from './SyncRunRow.svelte';

	let {
		runs,
		labelFor,
		providers = []
	}: {
		runs: SyncRunSummary[];
		labelFor: (provider: string) => string;
		/** Slugs the filter offers; fewer than two hides it. */
		providers?: string[];
	} = $props();

	const filter = shallowParam('sync', 'syncProvider');
	const selected = $derived(filter.current);

	const visible = $derived(
		runs.filter((run) => !selected || run.provider === selected).slice(0, RECENT_SHOWN)
	);

	const options = $derived([
		{ value: '', label: 'All providers' },
		...providers.map((provider) => ({ value: provider, label: labelFor(provider) }))
	]);
</script>

<Card
	title="Recent sync activity"
	description="The {RECENT_SHOWN} most recent runs; the buffer behind it only keeps 24 hours"
	bodyClass="p-0"
>
	{#snippet action()}
		{#if providers.length > 1}
			<FilterSelect
				label="Provider"
				value={selected}
				{options}
				onselect={(next) => filter.set(next)}
			/>
		{/if}
	{/snippet}

	{#if visible.length === 0}
		<EmptyState
			icon={History}
			title={selected ? 'Nothing from this provider in 24 hours' : 'Nothing in the last 24 hours'}
			description="This buffer only keeps a day. Completed backfills stay on the provider cards above."
		/>
	{:else}
		<ul class="divide-y divide-border">
			{#each visible as run (run.run_id)}
				<SyncRunRow {run} label={labelFor(run.provider)} />
			{/each}
		</ul>
	{/if}
</Card>

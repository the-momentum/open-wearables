<script lang="ts">
	import History from '@lucide/svelte/icons/history';
	import { pushState } from '$app/navigation';
	import { page } from '$app/state';
	import Card from '$lib/components/ui/Card.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import FilterSelect from '$lib/components/ui/FilterSelect.svelte';
	import { RECENT_SHOWN } from '$lib/syncs/recent';
	import type { SyncRunSummary } from '$lib/syncs/types';
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

	// pushState leaves page.url on the loaded page, so the choice lives in
	// page.state, which back and forward restore. The query string is read only
	// on arrival, for a shared or reloaded link.
	const selected = $derived(page.state.syncProvider ?? page.url.searchParams.get('sync') ?? '');

	const visible = $derived(
		runs.filter((run) => !selected || run.provider === selected).slice(0, RECENT_SHOWN)
	);

	const options = $derived([
		{ value: '', label: 'All providers' },
		...providers.map((provider) => ({ value: provider, label: labelFor(provider) }))
	]);

	function choose(provider: string) {
		const url = new URL(page.url);
		if (provider) url.searchParams.set('sync', provider);
		else url.searchParams.delete('sync');
		// Built from page.url, so the base path is already in it.
		// eslint-disable-next-line svelte/no-navigation-without-resolve
		pushState(url, { syncProvider: provider });
	}
</script>

<Card
	title="Recent sync activity"
	description="The {RECENT_SHOWN} most recent runs; the buffer behind it only keeps 24 hours"
	bodyClass="p-0"
>
	{#snippet action()}
		{#if providers.length > 1}
			<FilterSelect label="Provider" value={selected} {options} onselect={choose} />
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

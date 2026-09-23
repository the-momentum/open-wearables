<script lang="ts">
	import RefreshCw from '@lucide/svelte/icons/refresh-cw';
	import RefreshCcwDot from '@lucide/svelte/icons/refresh-ccw-dot';
	import { enhance } from '$app/forms';
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import PageHeader from '$lib/components/layout/PageHeader.svelte';
	import SyncFilters from '$lib/components/syncs/SyncFilters.svelte';
	import SyncOverview from '$lib/components/syncs/SyncOverview.svelte';
	import SyncRunItem from '$lib/components/syncs/SyncRunItem.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import Pagination from '$lib/components/ui/Pagination.svelte';
	import { FOOTNOTE, INLINE_LINK, MICRO } from '$lib/components/ui/typography';
	import { providerLabel } from '$lib/providers/labels';
	import { offsetHrefs } from '$lib/lists/offset';
	import { filtered, SYNC_WINDOW } from '$lib/syncs/runs';
	import { formatRelativeTime } from '$lib/utils/datetime';
	import { createSubmitFlag } from '$lib/utils/forms.svelte';
	import { formatNumber } from '$lib/utils/format';
	import { plural } from '$lib/utils/text';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const { hrefFor, pageHref, sizeHref, stepHrefs } = $derived(offsetHrefs(page.url));

	const label = (provider: string) => providerLabel(data.providers, provider);
	const pages = $derived(Math.max(Math.ceil(data.total / data.size), 1));
	const isFiltered = $derived(filtered(data.filters));
	const refresh = createSubmitFlag();
</script>

<div class="flex flex-col gap-5">
	<PageHeader
		title="Syncs"
		description="Every user's syncs from the last 24 hours, as Redis holds them."
	>
		{#snippet actions()}
			<form
				method="POST"
				action="?/refresh"
				use:enhance={refresh.enhance}
				class="flex items-center gap-3"
			>
				{#each Object.entries(data.filters) as [name, value] (name)}
					<input type="hidden" {name} {value} />
				{/each}
				<span class={MICRO}>Updated {formatRelativeTime(data.fetchedAt).toLowerCase()}</span>
				<Button type="submit" variant="outline" size="sm" disabled={refresh.submitting}>
					<RefreshCw
						size={13}
						aria-hidden="true"
						class={refresh.submitting ? 'animate-spin' : ''}
					/>
					Refresh
				</Button>
			</form>
		{/snippet}
	</PageHeader>

	<Card>
		<div class="flex flex-col gap-3">
			<SyncOverview counts={data.overview} />
			<p class={FOOTNOTE}>
				{plural(data.total, 'sync')} from {plural(data.overview.users, 'user')}{#if data.capped}
					— the newest {formatNumber(SYNC_WINDOW)}; more ran than one window holds, so narrow the
					filters to see the rest{/if}.
			</p>
		</div>
	</Card>

	<SyncFilters filters={data.filters} providers={data.providers} {hrefFor} />

	{#if data.runs.length === 0}
		<Card>
			<EmptyState
				icon={RefreshCcwDot}
				title={isFiltered ? 'No syncs match these filters' : 'No syncs in the last 24 hours'}
				description={isFiltered
					? 'Clear a filter, or widen the one on the user.'
					: 'Nothing has synced in the last day. Runs older than that have left the buffer.'}
			/>
		</Card>
	{:else}
		<Card bodyClass="p-0 sm:p-0">
			<ul class="divide-y divide-border">
				{#each data.runs as run (run.run_id)}
					<SyncRunItem {run} label={label(run.provider)} />
				{/each}
			</ul>
		</Card>

		<Pagination
			page={data.page}
			size={data.size}
			total={data.total}
			{...stepHrefs(data.page, pages)}
			hrefFor={pageHref}
			sizeHrefFor={sizeHref}
			noun="syncs"
		/>
	{/if}

	<p class={FOOTNOTE}>
		Backfills are also stored in Postgres with no time limit, but only per user: open a run above
		for its stored record, or a user in
		<a href={resolve('/users')} class={INLINE_LINK}>Users</a> for their whole history.
	</p>
</div>

<script lang="ts">
	import Moon from '@lucide/svelte/icons/moon';
	import { page } from '$app/state';
	import FilterBar from '$lib/components/filters/FilterBar.svelte';
	import FilterGroup from '$lib/components/filters/FilterGroup.svelte';
	import SleepCard from '$lib/components/sleep/SleepCard.svelte';
	import SleepSummary from '$lib/components/sleep/SleepSummary.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import CursorBar from '$lib/components/events/CursorBar.svelte';
	import DeleteEventDialog from '$lib/components/events/DeleteEventDialog.svelte';
	import Segmented from '$lib/components/ui/Segmented.svelte';
	import { providerLabel } from '$lib/providers/labels';
	import type { SleepSession } from '$lib/sleep/types';
	import { cursorHrefs } from '$lib/lists/cursor';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const nav = $derived(cursorHrefs(page.url));
	const { hrefFor } = $derived(nav);

	const label = (entry: string) => providerLabel(data.providers, entry);
	const connected = $derived(data.connections.map((connection) => connection.provider));

	const sessions = $derived(data.sessions.data);
	const filtered = $derived(Boolean(data.provider || data.topSourceOnly || data.period.from));

	let removing = $state<SleepSession | null>(null);
	let removeOpen = $state(false);
</script>

<div class="flex flex-col gap-6">
	<FilterBar
		period={data.period}
		{hrefFor}
		providers={connected}
		labelFor={label}
		selected={data.provider}
	>
		<!-- Two watches can both claim one night. This is the same ranking the
		     summaries use, and it answers "why are there two of these". -->
		<FilterGroup label="Sources">
			<Segmented
				label="Sources"
				selected={data.topSourceOnly ? 'top' : 'all'}
				items={[
					{ value: 'all', label: 'All', href: hrefFor({ top: null }) },
					{ value: 'top', label: 'Highest priority', href: hrefFor({ top: '1' }) }
				]}
			/>
		</FilterGroup>
	</FilterBar>

	<div class="flex flex-col gap-5 border-t border-border pt-6">
		<SleepSummary userId={page.params.id ?? ''} search={page.url.search} />

		{#if sessions.length === 0}
			<Card>
				<EmptyState
					icon={Moon}
					title={filtered ? 'No sessions match these filters' : 'No sleep recorded'}
					description={filtered
						? 'Widen the period, or clear the provider.'
						: 'Nothing this user’s providers have delivered is a sleep session.'}
				/>
			</Card>
		{:else}
			<div class="flex flex-col gap-3">
				{#each sessions as session (session.id)}
					<SleepCard
						{session}
						providerLabel={label(session.source.provider)}
						ondelete={() => {
							removing = session;
							removeOpen = true;
						}}
					/>
				{/each}
			</div>

			<CursorBar {nav} pagination={data.sessions.pagination} size={data.pageSize} />
		{/if}
	</div>
</div>

<DeleteEventDialog
	bind:open={removeOpen}
	noun="sleep session"
	action="?/deleteSleep"
	field="session"
	id={removing?.id ?? ''}
/>

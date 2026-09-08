<script lang="ts">
	import Unplug from '@lucide/svelte/icons/unplug';
	import Card from '$lib/components/ui/Card.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import type { Connection } from '$lib/connections/types';
	import { providerLabel } from '$lib/providers/labels';
	import type { Provider } from '$lib/server/providers';
	import type { SyncRun } from '$lib/syncs/types';
	import ConnectionCard from './ConnectionCard.svelte';

	let {
		connections,
		providers,
		backfills,
		onrevoke,
		onpurge
	}: {
		connections: Connection[];
		providers: Provider[];
		backfills: SyncRun[];
		onrevoke: (connection: Connection) => void;
		onpurge: (connection: Connection) => void;
	} = $props();

	// Grouped once, not re-scanned per card.
	const byProvider = $derived(Map.groupBy(backfills, (run) => run.provider));
</script>

<Card
	title="Connected providers"
	description="Wearables and health platforms this user has linked"
	bodyClass={connections.length === 0 ? 'p-0' : undefined}
>
	{#if connections.length === 0}
		<EmptyState
			icon={Unplug}
			title="No providers connected"
			description="Nothing is delivering data for this user yet."
		/>
	{:else}
		<div class={connections.length > 1 ? 'grid gap-4 lg:grid-cols-2' : 'grid gap-4'}>
			{#each connections as connection (connection.id)}
				<ConnectionCard
					{connection}
					label={providerLabel(providers, connection.provider)}
					backfills={byProvider.get(connection.provider) ?? []}
					onrevoke={() => onrevoke(connection)}
					onpurge={() => onpurge(connection)}
				/>
			{/each}
		</div>
	{/if}
</Card>

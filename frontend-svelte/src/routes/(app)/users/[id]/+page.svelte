<script lang="ts">
	import Alert from '$lib/components/ui/Alert.svelte';
	import ConfirmDialog from '$lib/components/ui/ConfirmDialog.svelte';
	import ConnectionsCard from '$lib/components/users/connections/ConnectionsCard.svelte';
	import RecentSyncsCard from '$lib/components/syncs/RecentSyncsCard.svelte';
	import type { Connection } from '$lib/connections/types';
	import { providerLabel } from '$lib/providers/labels';
	import type { ActionData, PageData } from './$types';

	let { data, form }: { data: PageData; form: ActionData } = $props();

	let revoking = $state<Connection | null>(null);
	let purging = $state<Connection | null>(null);
	let revokeOpen = $state(false);
	let purgeOpen = $state(false);

	const CONNECTION_ACTIONS = ['syncNow', 'syncHistory', 'revokeConnection', 'purgeConnectionData'];

	// Sync and revoke have no dialog of their own to report into, so a failure
	// surfaces beside the cards it concerns.
	const failure = $derived(
		form && 'message' in form && CONNECTION_ACTIONS.includes(form.action) ? form.message : undefined
	);

	const label = (connection: Connection | null) =>
		connection ? providerLabel(data.providers, connection.provider) : '';
</script>

<div class="flex flex-col gap-4">
	{#if failure}
		<Alert>{failure}</Alert>
	{/if}

	<ConnectionsCard
		connections={data.connections}
		providers={data.providers}
		backfills={data.backfills}
		onrevoke={(connection) => {
			revoking = connection;
			revokeOpen = true;
		}}
		onpurge={(connection) => {
			purging = connection;
			purgeOpen = true;
		}}
	/>

	<RecentSyncsCard
		runs={data.recentRuns}
		providers={data.connections.map((connection) => connection.provider)}
		labelFor={(provider) => providerLabel(data.providers, provider)}
	/>
</div>

{#if revoking}
	<ConfirmDialog
		bind:open={revokeOpen}
		title="Revoke connection"
		action="?/revokeConnection"
		confirmLabel="Revoke"
		busyLabel="Revoking…"
		fields={{ provider: revoking.provider }}
	>
		Revoke the <span class="font-medium">{label(revoking)}</span> connection? Syncing stops and the tokens
		are cleared. Data already collected stays.
	</ConfirmDialog>
{/if}

{#if purging}
	<ConfirmDialog
		bind:open={purgeOpen}
		title="Delete all data"
		action="?/purgeConnectionData"
		confirmLabel="Delete all data"
		busyLabel="Deleting…"
		fields={{ provider: purging.provider }}
		destructive
	>
		Delete everything <span class="font-medium">{label(purging)}</span> has delivered, and revoke the
		connection? This cannot be undone.
	</ConfirmDialog>
{/if}

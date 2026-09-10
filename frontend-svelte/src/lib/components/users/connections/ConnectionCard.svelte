<script lang="ts">
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import type { Connection } from '$lib/connections/types';
	import type { SyncRun } from '$lib/syncs/types';
	import BackfillList from './BackfillList.svelte';
	import ConnectionHeader from './ConnectionHeader.svelte';
	import ConnectionRoutes from './ConnectionRoutes.svelte';

	let {
		connection,
		label,
		backfills,
		onrevoke,
		onpurge
	}: {
		connection: Connection;
		label: string;
		backfills: SyncRun[];
		onrevoke: () => void;
		onpurge: () => void;
	} = $props();

	const shared = $derived(connection.linked_user_ids.length);
</script>

<article class="flex flex-col gap-3 rounded-xl border border-border bg-background p-4">
	<ConnectionHeader {connection} {label} {onrevoke} {onpurge} />

	<ConnectionRoutes {connection} />

	{#if shared > 0}
		<p class="text-xs text-muted-foreground">
			Shares this provider account with {shared} other profile{shared === 1 ? '' : 's'}.
		</p>
	{/if}

	<!-- Native details: no state to hold, and it stays open across a form action
	     because the element is never replaced. -->
	<details class="group mt-auto border-t border-border pt-3">
		<summary
			class="flex cursor-pointer list-none items-center justify-between text-xs text-muted-foreground transition-colors hover:text-foreground"
		>
			<span>
				Historical backfill log
				<span class="tabular-nums">({backfills.length})</span>
			</span>
			<ChevronDown
				size={15}
				aria-hidden="true"
				class="transition-transform group-open:rotate-180"
			/>
		</summary>

		<div class="mt-2.5">
			{#if backfills.length === 0}
				<p class="text-xs text-muted-foreground">
					No stored backfill for this provider. Live syncs are not kept here — see recent activity
					below.
				</p>
			{:else}
				<BackfillList runs={backfills} />
			{/if}
		</div>
	</details>
</article>

<script lang="ts">
	import type { Connection } from '$lib/connections/types';
	import HistoryRoute from './HistoryRoute.svelte';
	import LiveRoute from './LiveRoute.svelte';

	let { connection }: { connection: Connection } = $props();

	// Nothing to trigger on a connection that is no longer authorised.
	const actionable = $derived(connection.status === 'active');
</script>

<div
	class="-mx-1 grid divide-y divide-border/60 border-t border-border/60 pt-1
		sm:grid-cols-2 sm:divide-x sm:divide-y-0"
>
	<LiveRoute {connection} {actionable} />
	<HistoryRoute {connection} {actionable} />
</div>

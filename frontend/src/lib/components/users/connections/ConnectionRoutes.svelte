<script lang="ts">
	import type { Connection } from '$lib/connections/types';
	import HistoryRoute from './HistoryRoute.svelte';
	import LiveRoute from './LiveRoute.svelte';

	let { connection, viaSdk = false }: { connection: Connection; viaSdk?: boolean } = $props();

	// Nothing to trigger on a connection that is no longer authorised.
	const actionable = $derived(connection.status === 'active');
</script>

<div
	class="grid divide-y divide-border border-t border-border sm:grid-cols-2 sm:divide-x
		sm:divide-y-0 sm:pt-1"
>
	<LiveRoute {connection} {actionable} {viaSdk} />
	<HistoryRoute {connection} {actionable} {viaSdk} />
</div>

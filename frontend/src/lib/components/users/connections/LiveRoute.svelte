<script lang="ts">
	import RefreshCw from '@lucide/svelte/icons/refresh-cw';
	import Zap from '@lucide/svelte/icons/zap';
	import { enhance } from '$app/forms';
	import Button from '$lib/components/ui/Button.svelte';
	import { ICON } from '$lib/components/ui/icon';
	import StatePlate from '$lib/components/ui/StatePlate.svelte';
	import { SDK_DELIVERY, canForceLiveSync, liveDelivery } from '$lib/connections/delivery';
	import type { Connection } from '$lib/connections/types';
	import { createSubmitFlag } from '$lib/utils/forms.svelte';
	import RoutePane from './RoutePane.svelte';

	let {
		connection,
		actionable,
		viaSdk = false
	}: { connection: Connection; actionable: boolean; viaSdk?: boolean } = $props();

	const submit = createSubmitFlag();
	const forceable = $derived(actionable && canForceLiveSync(connection));
</script>

<RoutePane
	icon={Zap}
	heading="Live sync"
	hint={viaSdk ? SDK_DELIVERY.live.hint : forceable ? liveDelivery(connection) : null}
>
	{#if forceable}
		<form method="POST" action="?/syncNow" use:enhance={submit.enhance} class="sm:w-full">
			<input type="hidden" name="provider" value={connection.provider} />
			<Button variant="outline" type="submit" disabled={submit.submitting} class="sm:w-full">
				<RefreshCw size={ICON.sm} aria-hidden="true" />
				{submit.submitting ? 'Syncing…' : 'Sync now'}
			</Button>
		</form>
	{:else}
		<StatePlate>{viaSdk ? SDK_DELIVERY.live.label : liveDelivery(connection)}</StatePlate>
	{/if}
</RoutePane>

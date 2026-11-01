<script lang="ts">
	import { resolve } from '$app/paths';
	import Skeleton from '$lib/components/ui/Skeleton.svelte';
	import { MICRO, NOTE } from '$lib/components/ui/typography';
	import { resource } from '$lib/utils/resource.svelte';
	import type { Delivery, WebhookPage } from '$lib/webhooks/types';
	import DeliveryRow from './DeliveryRow.svelte';

	let { id }: { id: string } = $props();

	const fetched = resource<WebhookPage<Delivery>>(() => `/webhooks/${id}/recent`);
	const deliveries = $derived(fetched.current?.data ?? []);
</script>

{#if !fetched.settled}
	<Skeleton class="h-20" />
{:else if deliveries.length === 0}
	<p class={NOTE}>Nothing has been delivered to this subscription yet.</p>
{:else}
	<div class="flex flex-col gap-2">
		<div class="divide-y divide-border">
			{#each deliveries as delivery (delivery.id)}
				<DeliveryRow {delivery} />
			{/each}
		</div>

		<a
			href={resolve(`/webhooks/${id}/deliveries`)}
			class="{MICRO} self-start transition-colors hover:text-primary"
		>
			All deliveries →
		</a>
	</div>
{/if}

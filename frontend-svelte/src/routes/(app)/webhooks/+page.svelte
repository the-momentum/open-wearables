<script lang="ts">
	import Plus from '@lucide/svelte/icons/plus';
	import Webhook from '@lucide/svelte/icons/webhook';
	import Button from '$lib/components/ui/Button.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import ConfirmDialog from '$lib/components/ui/ConfirmDialog.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import PageHeader from '$lib/components/layout/PageHeader.svelte';
	import SubscriptionCard from '$lib/components/webhooks/SubscriptionCard.svelte';
	import SubscriptionDialog from '$lib/components/webhooks/SubscriptionDialog.svelte';
	import type { Subscription } from '$lib/webhooks/types';
	import type { ActionData, PageData } from './$types';
	import { messageFrom } from '$lib/utils/forms.svelte';

	let { data, form }: { data: PageData; form: ActionData } = $props();

	// One dialog of each kind for the page, not one per row, and the subject is
	// separate from openness so closing does not have to null it.
	let editing = $state<Subscription | null>(null);
	let formOpen = $state(false);
	let removing = $state<Subscription | null>(null);
	let removeOpen = $state(false);

	const messageFor = (action: string, id?: string) => messageFrom(form, action, id);

	function open(subscription: Subscription | null) {
		editing = subscription;
		formOpen = true;
	}
</script>

<div class="flex flex-col gap-5">
	<!-- Named for what it is: a standing request to be told about events.
	     "Webhooks" alone reads as something already running. -->
	<PageHeader
		title="Webhook subscriptions"
		description="Each one asks us to POST events to a URL of yours as they happen."
	>
		{#snippet actions()}
			<Button onclick={() => open(null)}>
				<Plus size={15} aria-hidden="true" />
				New subscription
			</Button>
		{/snippet}
	</PageHeader>

	{#if data.subscriptions.length === 0}
		<Card>
			<EmptyState
				icon={Webhook}
				title="No subscriptions yet"
				description="Create one to have events posted to your own service as they happen, rather than polling for them."
			/>
		</Card>
	{:else}
		<div class="flex flex-col gap-3 border-t border-border pt-5">
			{#each data.subscriptions as subscription (subscription.id)}
				<SubscriptionCard
					{subscription}
					types={data.types}
					testMessage={messageFor('test', subscription.id)}
					onedit={() => open(subscription)}
					ondelete={() => {
						removing = subscription;
						removeOpen = true;
					}}
				/>
			{/each}
		</div>
	{/if}
</div>

<SubscriptionDialog
	bind:open={formOpen}
	subscription={editing}
	types={data.types}
	message={messageFor(editing ? 'update' : 'create')}
/>

<ConfirmDialog
	bind:open={removeOpen}
	title="Delete subscription?"
	action="?/delete"
	confirmLabel="Delete"
	busyLabel="Deleting…"
	destructive
	fields={{ id: removing?.id ?? '' }}
>
	Events stop being posted to {removing?.url ?? 'this URL'} straight away. Deliveries already made are
	kept by the webhook service until it expires them.
</ConfirmDialog>

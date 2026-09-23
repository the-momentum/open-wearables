<script lang="ts">
	import Pencil from '@lucide/svelte/icons/pencil';
	import Send from '@lucide/svelte/icons/send';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import Webhook from '@lucide/svelte/icons/webhook';
	import { resolve } from '$app/paths';
	import AccordionCard from '$lib/components/events/AccordionCard.svelte';
	import Badge from '$lib/components/ui/Badge.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import IconButton from '$lib/components/ui/IconButton.svelte';
	import LinkButton from '$lib/components/ui/LinkButton.svelte';
	import { HEADING, MICRO } from '$lib/components/ui/typography';
	import type { EventType, Subscription } from '$lib/webhooks/types';
	import RecentDeliveries from './RecentDeliveries.svelte';
	import { summarise } from '$lib/webhooks/events';
	import { plural } from '$lib/utils/text';
	import EventList from './EventList.svelte';
	import SubscriptionEvents from './SubscriptionEvents.svelte';
	import TestEvent from './TestEvent.svelte';

	let {
		subscription,
		types,
		testMessage,
		onedit,
		ondelete
	}: {
		subscription: Subscription;
		types: EventType[];
		testMessage?: string;
		onedit: () => void;
		ondelete: () => void;
	} = $props();

	const filters = $derived(subscription.filter_types ?? []);
	const groups = $derived(summarise(filters, types));
	const named = $derived(subscription.description?.trim());

	const quiet = 'text-muted-foreground hover:text-foreground';
</script>

<AccordionCard icon={Webhook}>
	{#snippet title()}
		<span class={HEADING}>{named || subscription.url}</span>
	{/snippet}

	{#snippet when()}
		{#if named}<span class="{MICRO} truncate">{subscription.url}</span>{/if}
	{/snippet}

	{#snippet aside()}
		<Badge>{filters.length === 0 ? 'All events' : plural(filters.length, 'event')}</Badge>
	{/snippet}

	{#snippet metrics()}
		<div class="flex flex-wrap items-center justify-between gap-3">
			<div class="flex min-w-0 flex-wrap items-center gap-1.5">
				<SubscriptionEvents {groups} />
				{#if subscription.user_id}
					<!-- No leading separator with nothing before it: a subscription to
					     every event has no chips for the dot to follow. -->
					<span class={MICRO}>{filters.length > 0 ? '· ' : ''}one user only</span>
				{/if}
			</div>

			<!-- Controls, so the card's own click handler leaves them alone. -->
			<div class="flex shrink-0 items-center gap-1.5">
				<Button variant="outline" size="sm" onclick={onedit} class={quiet}>
					<Pencil size={13} aria-hidden="true" />
					Edit
				</Button>

				<LinkButton
					variant="outline"
					size="sm"
					href={resolve(`/webhooks/${subscription.id}/deliveries`)}
					class={quiet}
				>
					<Send size={13} aria-hidden="true" />
					Deliveries
				</LinkButton>

				<IconButton
					icon={Trash2}
					label="Delete subscription"
					danger
					onclick={ondelete}
					class={quiet}
				/>
			</div>
		</div>
	{/snippet}

	{#snippet details()}
		<div class="flex flex-col gap-4 border-t border-border pt-4">
			<EventList {groups} />

			<!-- Above the list on purpose: what you send lands in it. -->
			<TestEvent {subscription} {types} message={testMessage} />

			<div class="flex flex-col gap-2">
				<span class={MICRO}>Recent deliveries</span>
				<RecentDeliveries id={subscription.id} />
			</div>
		</div>
	{/snippet}
</AccordionCard>

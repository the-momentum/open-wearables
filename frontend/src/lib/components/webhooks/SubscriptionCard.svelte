<script lang="ts">
	import Pencil from '@lucide/svelte/icons/pencil';
	import Send from '@lucide/svelte/icons/send';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import Webhook from '@lucide/svelte/icons/webhook';
	import { resolve } from '$app/paths';
	import { togglesCard } from '$lib/components/events/accordion';
	import Button from '$lib/components/ui/Button.svelte';
	import ExpandChevron from '$lib/components/ui/ExpandChevron.svelte';
	import { ICON } from '$lib/components/ui/icon';
	import IconButton from '$lib/components/ui/IconButton.svelte';
	import LinkButton from '$lib/components/ui/LinkButton.svelte';
	import { HEADING, MICRO } from '$lib/components/ui/typography';
	import { cn } from '$lib/utils/cn';
	import { plural } from '$lib/utils/text';
	import { summarise } from '$lib/webhooks/events';
	import type { EventType, Subscription } from '$lib/webhooks/types';
	import EventList from './EventList.svelte';
	import RecentDeliveries from './RecentDeliveries.svelte';
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

	let open = $state(false);
	const panelId = $props.id();

	const filters = $derived(subscription.filter_types ?? []);
	const groups = $derived(summarise(filters, types));
	const named = $derived(subscription.description?.trim());

	const toggle = (event: MouseEvent) => {
		if (togglesCard(event)) open = !open;
	};
</script>

<!-- The heading's button is what the keyboard and assistive tech drive; the
     handler only widens the pointer target to the whole card, as AccordionCard
     does. Its own anatomy differs: the actions share the header row, and the
     open card is outlined rather than split by an edge-to-edge rule. -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<article
	onclick={toggle}
	class={cn(
		'group flex cursor-pointer flex-col gap-3 rounded-lg border bg-card p-4 transition-colors',
		open ? 'border-primary/40' : 'border-border'
	)}
>
	<!-- A phone puts the actions on a row of their own, under the URL. -->
	<div
		class="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-3 sm:grid-cols-[minmax(0,1fr)_auto_auto] sm:items-center"
	>
		<h3 class="min-w-0">
			<button
				type="button"
				data-accordion-toggle
				aria-expanded={open}
				aria-controls={panelId}
				class="flex w-full cursor-pointer items-center gap-3 text-left"
			>
				<span
					aria-hidden="true"
					class="grid size-9 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary"
				>
					<Webhook size={ICON.md} />
				</span>
				<span class="flex min-w-0 flex-col gap-0.5">
					<span class="{HEADING} break-words">{named || subscription.url}</span>
					{#if named}<span class="{MICRO} break-words">{subscription.url}</span>{/if}
				</span>
			</button>
		</h3>

		<div class="col-span-2 row-start-2 flex items-center gap-1.5 sm:col-span-1 sm:row-start-auto">
			<IconButton
				icon={Trash2}
				label="Delete subscription"
				danger
				onclick={ondelete}
				class="border border-border text-foreground"
			/>
			<Button variant="outline" size="sm" onclick={onedit} class="max-sm:flex-1">
				<Pencil size={ICON.xs} aria-hidden="true" />
				Edit
			</Button>
			<LinkButton
				variant="outline"
				size="sm"
				href={resolve(`/webhooks/${subscription.id}/deliveries`)}
				class="max-sm:flex-1"
			>
				<Send size={ICON.xs} aria-hidden="true" />
				Deliveries
			</LinkButton>
		</div>

		<ExpandChevron {open} boxed class="col-start-2 row-start-1 sm:col-start-3" />
	</div>

	{#if filters.length > 0 || subscription.user_id}
		<div class="flex min-w-0 flex-wrap items-center gap-1.5">
			{#if filters.length > 0}
				<span class={MICRO}>{plural(filters.length, 'event')}</span>
				<SubscriptionEvents {groups} />
			{/if}
			{#if subscription.user_id}
				<!-- No leading separator with nothing before it: a subscription to
				     every event has no chips for the dot to follow. -->
				<span class={MICRO}>{filters.length > 0 ? '· ' : ''}one user only</span>
			{/if}
		</div>
	{/if}

	{#if open}
		<!-- Its own thing: selecting a value or following a link inside must not
		     fold the card away underneath. -->
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div
			id={panelId}
			class="flex cursor-auto flex-col gap-3"
			onclick={(event) => event.stopPropagation()}
		>
			<hr class="border-border" />
			<!-- Side by side: what you send lands in what it listens to. -->
			<div class="grid gap-3 sm:grid-cols-2 sm:gap-8">
				<EventList {groups} />
				<TestEvent {subscription} {types} message={testMessage} />
			</div>
			<hr class="border-border" />
			<div class="flex flex-col gap-2">
				<span class={MICRO}>Recent deliveries</span>
				<RecentDeliveries id={subscription.id} />
			</div>
		</div>
	{/if}
</article>

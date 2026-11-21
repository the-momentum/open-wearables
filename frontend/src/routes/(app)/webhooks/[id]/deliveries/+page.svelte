<script lang="ts">
	import Send from '@lucide/svelte/icons/send';
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import BackLink from '$lib/components/ui/BackLink.svelte';
	import Caption from '$lib/components/ui/Caption.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import Pagination from '$lib/components/ui/Pagination.svelte';
	import { LIST_FRAME, LIST_ROW } from '$lib/components/ui/table';
	import PageHeader from '$lib/components/layout/PageHeader.svelte';
	import DeliveryFilters from '$lib/components/webhooks/DeliveryFilters.svelte';
	import DeliveryRow from '$lib/components/webhooks/DeliveryRow.svelte';
	import { cn } from '$lib/utils/cn';
	import { grouped } from '$lib/utils/collect';
	import { formatLocalDate, localDayKey } from '$lib/utils/format';
	import { cursorHrefs } from '$lib/lists/cursor';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	// The same keyset wiring the event lists use, under Svix's parameter name.
	const nav = $derived(cursorHrefs(page.url, 'iterator'));
	const hrefFor = $derived(nav.hrefFor);

	const deliveries = $derived(data.deliveries.data);

	// By the day they were attempted: a page of forty timestamps is a wall, and
	// "did anything go out yesterday" is the question being asked of it.
	const days = $derived(grouped(deliveries, (attempt) => localDayKey(attempt.timestamp, null)));
</script>

<div class="lg:border-b lg:border-border lg:pb-5">
	<PageHeader title="Deliveries" description={data.subscription.url} truncate>
		{#snippet above()}
			<BackLink href={resolve('/webhooks')}>Webhook subscriptions</BackLink>
		{/snippet}
	</PageHeader>
</div>

<DeliveryFilters
	status={data.filters.status}
	eventType={data.filters.eventTypes[0] ?? ''}
	types={data.types}
	{hrefFor}
/>

{#if deliveries.length === 0}
	<Card>
		<EmptyState
			icon={Send}
			title="No deliveries match"
			description="Nothing has been sent to this subscription under these filters."
		/>
	</Card>
{:else}
	{#each days as group (group.key)}
		<section class="flex flex-col gap-2">
			<Caption>{formatLocalDate(`${group.key}T00:00:00Z`, null)}</Caption>
			<ul class="overflow-hidden {LIST_FRAME}">
				{#each group.items as delivery (delivery.id)}
					<!-- Lit on its summary only: the open panel below it is not a target. -->
					<li class={cn(LIST_ROW, 'hover:bg-transparent')}>
						<DeliveryRow {delivery} expandable />
					</li>
				{/each}
			</ul>
		</section>
	{/each}

	<!-- `total` is null: Svix counts nothing, so the bar marks the position and
	     steps rather than claiming a last page. -->
	<Pagination
		page={nav.at}
		size={data.limit}
		total={null}
		previousHref={nav.stepHref(data.deliveries.prevIterator, -1)}
		nextHref={nav.stepHref(data.deliveries.done ? null : data.deliveries.iterator, 1)}
	/>
{/if}

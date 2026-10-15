<script lang="ts">
	import MonitorSmartphone from '@lucide/svelte/icons/monitor-smartphone';
	import { resolve } from '$app/paths';
	import SourceGroupCard from '$lib/components/sources/SourceGroupCard.svelte';
	import Caption from '$lib/components/ui/Caption.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import { FOOTNOTE, INLINE_LINK } from '$lib/components/ui/typography';
	import { brandOf } from '$lib/providers/labels';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	// Ranked first overall, so whenever it has data for a day, the summaries use it
	const preferredId = $derived(data.groups[0]?.sources[0]?.id ?? null);
</script>

{#if data.groups.length === 0}
	<Card>
		<EmptyState
			icon={MonitorSmartphone}
			title="No sources yet"
			description="A device or app shows up here with the first data it sends."
		/>
	</Card>
{:else}
	<div class="flex flex-col gap-2">
		<Caption>In priority order</Caption>
		<div class="flex flex-col gap-3">
			{#each data.groups as group (group.provider)}
				<SourceGroupCard {group} brand={brandOf(data.providers, group.provider)} {preferredId} />
			{/each}
		</div>
		<p class={FOOTNOTE}>
			Where sources cover the same day, summaries use the one higher in this order.
			<a href={resolve('/settings/priorities')} class={INLINE_LINK}>Change the order</a>
		</p>
	</div>
{/if}

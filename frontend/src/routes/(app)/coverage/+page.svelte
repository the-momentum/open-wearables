<script lang="ts">
	import Grid from '@lucide/svelte/icons/grid-2x2';
	import { page } from '$app/state';
	import CapabilityRow from '$lib/components/coverage/CapabilityRow.svelte';
	import CoverageFilters from '$lib/components/coverage/CoverageFilters.svelte';
	import CountRanking from '$lib/components/summary/CountRanking.svelte';
	import Caption from '$lib/components/ui/Caption.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import { MICRO } from '$lib/components/ui/typography';
	import { capabilities, filterCapabilities, providerTotals } from '$lib/coverage/rows';
	import { providerLabel } from '$lib/providers/labels';
	import { grouped } from '$lib/utils/collect';
	import { formatShare } from '$lib/utils/format';
	import { withParams } from '$lib/utils/url';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const hrefFor = (changes: Record<string, string | null>) => withParams(page.url, changes);
	const label = (provider: string) => providerLabel(data.providers, provider);

	const all = $derived(capabilities(data.coverage));
	const shown = $derived(filterCapabilities(all, data.filters));
	const total = $derived(data.coverage.providers.length);
</script>

<div class="flex flex-col gap-5">
	<Card
		title="What each provider can deliver"
		description="Capabilities as written in the integrations, not what your users have synced."
	>
		<!-- Counted over the whole matrix, so the ranking says how much of it an
		     integration covers rather than how many rows it appears in. -->
		<CountRanking
			counts={providerTotals(all)}
			limit={total}
			labelFor={label}
			format={(count) => formatShare(count, all.length)}
		/>
	</Card>

	<CoverageFilters
		filters={data.filters}
		providers={data.coverage.providers}
		labelFor={label}
		{hrefFor}
	/>

	<div class="flex flex-col gap-5 border-t border-border pt-5">
		<p class={MICRO}>{shown.length} of {all.length} capabilities · {total} providers</p>

		{#if shown.length === 0}
			<Card>
				<EmptyState
					icon={Grid}
					title="Nothing matches"
					description="No capability in this layer answers to that name."
				/>
			</Card>
		{:else}
			{#each grouped(shown, (row) => row.group) as group (group.key)}
				<section class="flex flex-col gap-1">
					<Caption>{group.key}</Caption>
					<div class="divide-y divide-border">
						{#each group.items as row (row.code)}
							<CapabilityRow {row} {total} labelFor={label} />
						{/each}
					</div>
				</section>
			{/each}
		{/if}
	</div>
</div>

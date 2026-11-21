<script lang="ts">
	import LayoutGrid from '@lucide/svelte/icons/layout-grid';
	import { page } from '$app/state';
	import CapabilityRow from '$lib/components/coverage/CapabilityRow.svelte';
	import CoverageFilters from '$lib/components/coverage/CoverageFilters.svelte';
	import ProviderCoverage from '$lib/components/coverage/ProviderCoverage.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import { LIST_FRAME } from '$lib/components/ui/table';
	import { HEADING, MICRO } from '$lib/components/ui/typography';
	import { capabilities, filterCapabilities, providerTotals } from '$lib/coverage/rows';
	import { brandOf, providerLabel } from '$lib/providers/labels';
	import { grouped } from '$lib/utils/collect';
	import { withParams } from '$lib/utils/url';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const hrefFor = (changes: Record<string, string | null>) => withParams(page.url, changes);
	const label = (provider: string) => providerLabel(data.providers, provider);
	const brand = (provider: string) => brandOf(data.providers, provider);

	const all = $derived(capabilities(data.coverage));
	const shown = $derived(filterCapabilities(all, data.filters));
	const total = $derived(data.coverage.providers.length);
</script>

<ProviderCoverage totals={providerTotals(all)} capabilities={all.length} labelFor={label} />

<CoverageFilters
	filters={data.filters}
	providers={data.coverage.providers}
	labelFor={label}
	{hrefFor}
/>

<div class="flex flex-col gap-4">
	<p class="flex gap-1.5 {MICRO}">
		<span>{shown.length} of {all.length} capabilities</span>
		<span>{total} providers</span>
	</p>

	{#if shown.length === 0}
		<Card>
			<EmptyState
				icon={LayoutGrid}
				title="Nothing matches"
				description="No capability in this layer answers to that name."
			/>
		</Card>
	{:else}
		{#each grouped(shown, (row) => row.group) as group (group.key)}
			<section class="flex flex-col gap-3">
				<h2 class={HEADING}>{group.key}</h2>
				<div class="p-3 {LIST_FRAME}">
					{#each group.items as row (row.code)}
						<CapabilityRow {row} {total} brandFor={brand} />
					{/each}
				</div>
			</section>
		{/each}
	{/if}
</div>

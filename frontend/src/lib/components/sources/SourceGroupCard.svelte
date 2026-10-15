<script lang="ts">
	import ProviderLogo from '$lib/components/providers/ProviderLogo.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import { MICRO } from '$lib/components/ui/typography';
	import type { ProviderBrand } from '$lib/providers/labels';
	import type { SourceGroup } from '$lib/sources/types';
	import SourceRow from './SourceRow.svelte';

	let {
		group,
		brand,
		preferredId
	}: { group: SourceGroup; brand: ProviderBrand; preferredId: string | null } = $props();

	const count = $derived(group.sources.length);
</script>

<Card title={brand.name} bodyClass="p-0 sm:p-0">
	{#snippet leading()}
		<ProviderLogo provider={brand} size="xs" />
	{/snippet}
	{#snippet action()}
		<span class={MICRO}>{count} {count === 1 ? 'source' : 'sources'}</span>
	{/snippet}
	<ul class="divide-y divide-border">
		{#each group.sources as source (source.id)}
			<SourceRow {source} preferred={source.id === preferredId} />
		{/each}
	</ul>
</Card>

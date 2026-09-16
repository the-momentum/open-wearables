<script lang="ts">
	import { page } from '$app/state';
	import Card from '$lib/components/ui/Card.svelte';
	import { CAPTION } from '$lib/components/ui/typography';
	import CountRanking from '$lib/components/summary/CountRanking.svelte';
	import Heatmap from '$lib/components/summary/Heatmap.svelte';
	import ProviderShare from '$lib/components/summary/ProviderShare.svelte';
	import SummaryFilters from '$lib/components/summary/SummaryFilters.svelte';
	import SummaryTotals from '$lib/components/summary/SummaryTotals.svelte';
	import { providerLabel } from '$lib/providers/labels';
	import { narrowToProvider } from '$lib/summary/narrow';
	import { plottable } from '$lib/summary/period';
	import { humanise } from '$lib/utils/text';
	import { shallowParam } from '$lib/utils/shallow.svelte';
	import { withParams } from '$lib/utils/url';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const provider = shallowParam('provider', 'summaryProvider');
	const chosen = $derived(provider.current);

	// pushState leaves page.url on the loaded page, so the chosen provider is not
	// in it. Carrying it explicitly is what stops a period change from clearing
	// the filter.
	const hrefFor = (changes: Record<string, string | null>) =>
		withParams(page.url, { provider: chosen || null, ...changes });

	const label = (entry: string) => providerLabel(data.providers, entry);
	const connected = $derived(data.connections.map((connection) => connection.provider));

	const totals = $derived(chosen ? narrowToProvider(data.summary, chosen) : data.summary);

	// A single day has one bucket, so its panels fall back to bars.
	const overTime = $derived(plottable(data.period));

	const notSplit = 'the timeline is not split per provider';
</script>

<div class="flex flex-col gap-4">
	<SummaryFilters
		period={data.period}
		{hrefFor}
		providers={connected}
		labelFor={label}
		selected={chosen}
		onpick={(entry) => provider.set(entry)}
	/>

	<Card
		title="Data collected"
		description={chosen ? `From ${label(chosen)}` : 'Everything stored for this user'}
	>
		<div class="flex flex-col gap-5">
			<SummaryTotals summary={totals} />
			<ProviderShare providers={data.summary.by_provider} labelFor={label} selected={chosen} />

			{#if overTime && data.byProvider.series.length > 0}
				<div class="flex flex-col gap-2 border-t border-border pt-4">
					<span class={CAPTION}>
						Data points per {data.byProvider.bucket} — workouts and sleep are counted above, not here
					</span>
					<Heatmap timeline={data.byProvider} period={data.period} labelFor={label} only={chosen} />
				</div>
			{/if}
		</div>
	</Card>

	<!-- Narrowed to a provider, this can only be totals: the timeline endpoint
	     takes no provider, so plotting it would show every provider's data under
	     a heading that says otherwise. -->
	<Card
		title="Series types"
		description={chosen
			? `What ${label(chosen)} delivers — ${notSplit}`
			: overTime
				? `Data points per ${data.byType.bucket}, busiest first`
				: 'Measurements recorded that day'}
	>
		{#if overTime && !chosen}
			<Heatmap timeline={data.byType} period={data.period} labelFor={humanise} />
		{:else}
			<CountRanking counts={totals.series_type_counts} />
		{/if}
	</Card>

	<Card
		title="Workout types"
		description={chosen
			? `Across every provider — ${notSplit}`
			: 'Totals only — the timeline endpoint does not carry event records yet'}
	>
		<CountRanking counts={data.summary.workout_type_counts} limit={6} />
	</Card>
</div>

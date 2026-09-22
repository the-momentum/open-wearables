<script lang="ts">
	import { page } from '$app/state';
	import Card from '$lib/components/ui/Card.svelte';
	import { CAPTION } from '$lib/components/ui/typography';
	import Heatmap from '$lib/components/summary/Heatmap.svelte';
	import ShareBar from '$lib/components/charts/ShareBar.svelte';
	import FilterBar from '$lib/components/filters/FilterBar.svelte';
	import SummaryTotals from '$lib/components/summary/SummaryTotals.svelte';
	import TimelinePanel from '$lib/components/summary/TimelinePanel.svelte';
	import { providerLabel } from '$lib/providers/labels';
	import { narrowToProvider, providerParts } from '$lib/summary/narrow';
	import { plottable } from '$lib/filters/period';
	import { humanise } from '$lib/utils/text';
	import { withParams } from '$lib/utils/url';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const chosen = $derived(data.provider);
	const hrefFor = (changes: Record<string, string | null>) => withParams(page.url, changes);

	const label = (entry: string) => providerLabel(data.providers, entry);
	const connected = $derived(data.connections.map((connection) => connection.provider));

	const totals = $derived(chosen ? narrowToProvider(data.summary, chosen) : data.summary);

	// Only the wording branches here; the panels decide for themselves.
	const overTime = $derived(plottable(data.period));
	const from = $derived(chosen ? ` from ${label(chosen)}` : '');
</script>

<div class="flex flex-col gap-4">
	<FilterBar
		period={data.period}
		{hrefFor}
		providers={connected}
		labelFor={label}
		selected={chosen}
	/>

	<Card
		title="Data collected"
		description={chosen ? `From ${label(chosen)}` : 'Everything stored for this user'}
	>
		<div class="flex flex-col gap-5">
			<SummaryTotals summary={totals} />
			<ShareBar parts={providerParts(data.summary.by_provider, label)} selected={chosen} />

			<!-- Providers get a heatmap and never a ranking: the share bar above
			     already ranks them, and one day of one provider is a single bar. -->
			{#if overTime && data.byProvider.series.length > 0}
				<div class="flex flex-col gap-2 border-t border-border pt-4">
					<span class={CAPTION}>
						Data points per {data.byProvider.bucket} — workouts and sleep are counted above, not here
					</span>
					<Heatmap timeline={data.byProvider} period={data.period} labelFor={label} />
				</div>
			{/if}
		</div>
	</Card>

	<Card
		title="Series types"
		description={overTime
			? `Data points per ${data.byType.bucket}${from}, busiest first`
			: `Measurements recorded that day${from}`}
	>
		<TimelinePanel timeline={data.byType} period={data.period} labelFor={humanise} />
	</Card>

	<Card
		title="Workout types"
		description={overTime
			? `Workouts per ${data.byWorkout.bucket}${from}, most frequent first`
			: `Workouts recorded that day${from}`}
	>
		<TimelinePanel timeline={data.byWorkout} period={data.period} labelFor={humanise} limit={6} />
	</Card>
</div>

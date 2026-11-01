<script lang="ts">
	import { windowOf } from '$lib/charts/geometry';
	import Skeleton from '$lib/components/ui/Skeleton.svelte';
	import { MICRO, NOTE } from '$lib/components/ui/typography';
	import { knownCategory } from '$lib/scores/categories';
	import type { CategoryTrend } from '$lib/scores/trends';
	import { formatLocalDay } from '$lib/utils/format';
	import CategoryChart from './CategoryChart.svelte';
	import ScoreTrend from './ScoreTrend.svelte';

	let {
		trends,
		settled,
		truncated,
		category,
		hrefFor,
		colourFor
	}: {
		trends: CategoryTrend[];
		settled: boolean;
		/** The period held more scores than one page, so the window is short. */
		truncated: boolean;
		/** The category the list below is narrowed to, drawn large here. */
		category: string;
		hrefFor: (changes: Record<string, string | null>) => string;
		/** Shared with the cards below, so a provider keeps one colour. */
		colourFor: (provider: string) => string;
	} = $props();

	const chosen = $derived(trends.find((trend) => trend.category === category));

	// One window for every tile, so their shapes can be read against each other,
	// and unchanged when a category is picked so the axis does not jump.
	const window = $derived(windowOf(trends.flatMap((trend) => trend.lines)));

	const grid = 'grid gap-3 sm:grid-cols-2 lg:grid-cols-3';
	const day = (at: number) => formatLocalDay(new Date(at).toISOString(), null);
</script>

{#if !settled}
	<div class={grid}>
		{#each [1, 2, 3] as key (key)}
			<Skeleton class="h-40" />
		{/each}
	</div>
{:else if trends.length === 0}
	<p class={NOTE}>No score was recorded in this period.</p>
{:else if chosen}
	<CategoryChart trend={chosen} from={window.from} to={window.to} {colourFor} />
{:else}
	<div class={grid}>
		{#each trends as trend (trend.category)}
			<!-- The tiles are the chooser, so one is a link only where the API can be
			     asked to filter by it. -->
			<ScoreTrend
				{trend}
				from={window.from}
				to={window.to}
				{colourFor}
				href={knownCategory(trend.category) ? hrefFor({ category: trend.category }) : null}
			/>
		{/each}
	</div>
{/if}

{#if truncated}
	<!-- The window the trends actually cover, which is shorter than the one asked
	     for: a provider that samples all day fills a page in under a month. -->
	<p class={MICRO}>Trends: {day(window.from)} – {day(window.to)}</p>
{/if}

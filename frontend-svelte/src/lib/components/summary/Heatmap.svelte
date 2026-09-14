<script lang="ts">
	import ChartRow from '$lib/components/ui/ChartRow.svelte';
	import ShowAll from '$lib/components/ui/ShowAll.svelte';
	import { NOTE } from '$lib/components/ui/typography';
	import { periodWindow, type Period } from '$lib/summary/period';
	import { toRows } from '$lib/summary/timeline';
	import type { DataTimeline } from '$lib/summary/types';
	import HeatLegend from './HeatLegend.svelte';
	import HeatmapRow from './HeatmapRow.svelte';
	import MonthAxis from './MonthAxis.svelte';

	let {
		timeline,
		period,
		labelFor,
		only = '',
		limit = 12
	}: {
		timeline: DataTimeline;
		period: Period;
		labelFor: (key: string) => string;
		/** Keeps a single series, for when a filter has narrowed the page. */
		only?: string;
		limit?: number;
	} = $props();

	const shown = $derived(
		only ? { ...timeline, series: timeline.series.filter((entry) => entry.key === only) } : timeline
	);

	let expanded = $state(false);

	const grid = $derived(toRows(shown, periodWindow(period)));
	const rows = $derived(expanded ? grid.rows : grid.rows.slice(0, limit));
	const unit = $derived(shown.bucket === 'week' ? 'week of ' : '');
</script>

{#if grid.rows.length === 0}
	<p class={NOTE}>Nothing arrived in this period.</p>
{:else if grid.dates.length < 2}
	<p class={NOTE}>A single day has nothing to plot over time — pick a range.</p>
{:else}
	<div class="flex flex-col gap-3">
		<div class="flex flex-col gap-1.5">
			<ChartRow><MonthAxis dates={grid.dates} /></ChartRow>

			{#each rows as row (row.key)}
				<HeatmapRow {row} label={labelFor(row.key)} max={grid.max} {unit} />
			{/each}
		</div>

		<div class="flex flex-wrap items-center gap-x-3 gap-y-2">
			{#if grid.rows.length > limit}
				<ShowAll bind:expanded total={grid.rows.length} />
			{/if}
			<div class="ml-auto"><HeatLegend peak={grid.max} /></div>
		</div>
	</div>
{/if}

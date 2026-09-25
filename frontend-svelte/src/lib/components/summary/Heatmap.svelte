<script lang="ts">
	import ChartRow from '$lib/components/ui/ChartRow.svelte';
	import ShowAll from '$lib/components/ui/ShowAll.svelte';
	import { NOTE } from '$lib/components/ui/typography';
	import { periodWindow, type Period } from '$lib/filters/period';
	import { toRows } from '$lib/summary/timeline';
	import type { DataTimeline } from '$lib/summary/types';
	import HeatLegend from './HeatLegend.svelte';
	import HeatmapRow from './HeatmapRow.svelte';
	import MonthAxis from './MonthAxis.svelte';

	let {
		timeline,
		period,
		labelFor,
		limit = 12
	}: {
		timeline: DataTimeline;
		period: Period;
		labelFor: (key: string) => string;
		limit?: number;
	} = $props();

	let expanded = $state(false);

	const grid = $derived(toRows(timeline, periodWindow(period)));
	const rows = $derived(expanded ? grid.rows : grid.rows.slice(0, limit));
	const unit = $derived(timeline.bucket === 'week' ? 'week of ' : '');
</script>

{#if grid.rows.length === 0}
	<p class={NOTE}>Nothing arrived in this period.</p>
{:else if grid.dates.length < 2}
	<!-- Not a period the reader can widen: their whole history is this narrow. -->
	<p class={NOTE}>Everything this user has lands in one {timeline.bucket}.</p>
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

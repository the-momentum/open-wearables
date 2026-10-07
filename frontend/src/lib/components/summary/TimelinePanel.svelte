<script lang="ts">
	import { plottable, type Period } from '$lib/filters/period';
	import { totalsFromTimeline } from '$lib/summary/timeline';
	import type { DataTimeline } from '$lib/summary/types';
	import CountRanking from './CountRanking.svelte';
	import Heatmap from './Heatmap.svelte';

	let {
		timeline,
		period,
		labelFor,
		limit
	}: {
		timeline: DataTimeline;
		period: Period;
		labelFor: (key: string) => string;
		/** Rows before the expand toggle; each shape keeps its own default. */
		limit?: number;
	} = $props();
</script>

<!-- One bucket is not a timeline, so a single day is ranked rather than plotted.
     Both shapes read the same response, which is what stops a filter from
     narrowing one and leaving the other showing everyone. -->
{#if plottable(period)}
	<Heatmap {timeline} {period} {labelFor} {limit} />
{:else}
	<CountRanking counts={totalsFromTimeline(timeline)} {limit} />
{/if}

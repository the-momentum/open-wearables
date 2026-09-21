<script lang="ts">
	import LineChart from '$lib/components/charts/LineChart.svelte';
	import { MICRO } from '$lib/components/ui/typography';
	import { categoryLabel } from '$lib/scores/categories';
	import type { CategoryTrend } from '$lib/scores/trends';
	import { formatLocalDay, showDecimal } from '$lib/utils/format';

	let {
		trend,
		from,
		to,
		colourFor
	}: {
		trend: CategoryTrend;
		from: number;
		to: number;
		colourFor: (provider: string) => string;
	} = $props();

	const days = $derived(trend.days === 1 ? '1 day' : `${trend.days} days`);
</script>

<!-- Framed like a tile, because it stands where the tiles were: one category at
     full size, with the exact value under the pointer. -->
<div class="flex flex-col gap-2 rounded-xl border border-border bg-surface p-4">
	<LineChart
		series={trend.lines}
		zones={null}
		{from}
		{to}
		{colourFor}
		format={(value) => showDecimal(value)}
		shared
		formatTime={(at) => formatLocalDay(new Date(at).toISOString(), null)}
		label="{categoryLabel(trend.category)} score over the period"
	/>
	<p class="{MICRO} text-right">{days}</p>
</div>

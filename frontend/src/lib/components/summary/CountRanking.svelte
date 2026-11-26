<script lang="ts">
	import BarTrack from '$lib/components/charts/BarTrack.svelte';
	import ChartRow from '$lib/components/ui/ChartRow.svelte';
	import ShowAll from '$lib/components/ui/ShowAll.svelte';
	import { NOTE } from '$lib/components/ui/typography';
	import { formatNumber } from '$lib/utils/format';
	import { humanise } from '$lib/utils/text';

	let { counts, limit = 8 }: { counts: Record<string, number>; limit?: number } = $props();

	let expanded = $state(false);

	const rows = $derived(Object.entries(counts).sort(([, a], [, b]) => b - a));
	const shown = $derived(expanded ? rows : rows.slice(0, limit));
	// Bars are read against the leader, so the scale is its count, not the total.
	const top = $derived(rows[0]?.[1] ?? 0);
</script>

{#if rows.length === 0}
	<p class={NOTE}>Nothing recorded in this period.</p>
{:else}
	<div class="flex flex-col gap-2">
		<ul class="flex flex-col gap-1.5">
			{#each shown as [code, count] (code)}
				<li>
					<ChartRow label={humanise(code)} value={formatNumber(count)}>
						<BarTrack fraction={top === 0 ? 0 : count / top} />
					</ChartRow>
				</li>
			{/each}
		</ul>

		{#if rows.length > limit}
			<div class="self-start"><ShowAll bind:expanded total={rows.length} /></div>
		{/if}
	</div>
{/if}

<script lang="ts">
	import ChartRow from '$lib/components/ui/ChartRow.svelte';
	import ShowAll from '$lib/components/ui/ShowAll.svelte';
	import { NOTE } from '$lib/components/ui/typography';
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
					<ChartRow label={humanise(code)} value={count}>
						<span class="block h-2.5 overflow-hidden rounded-full bg-surface-muted">
							<span
								aria-hidden="true"
								class="block h-full rounded-full bg-gradient-to-r from-primary to-primary/55
									transition-[width] duration-300"
								style="width: {top === 0 ? 0 : (count / top) * 100}%"
							></span>
						</span>
					</ChartRow>
				</li>
			{/each}
		</ul>

		{#if rows.length > limit}
			<div class="self-start"><ShowAll bind:expanded total={rows.length} /></div>
		{/if}
	</div>
{/if}

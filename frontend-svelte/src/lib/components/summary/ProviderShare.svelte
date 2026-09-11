<script lang="ts">
	import { rankShade } from '$lib/summary/shades';
	import type { ProviderDataCount } from '$lib/summary/types';

	let {
		providers,
		labelFor,
		selected = ''
	}: {
		providers: ProviderDataCount[];
		labelFor: (provider: string) => string;
		/** Dims the rest, so the bar still says how big the chosen slice is. */
		selected?: string;
	} = $props();

	const dim = (provider: string) => selected !== '' && selected !== provider;

	// Every kind of record, so the bar answers "where does the data come from"
	// rather than "where do data points come from".
	const rows = $derived(
		providers
			.map((entry) => ({
				provider: entry.provider,
				total: entry.data_points + entry.workout_count + entry.sleep_count
			}))
			.filter((entry) => entry.total > 0)
			.sort((a, b) => b.total - a.total)
	);

	const grand = $derived(rows.reduce((sum, row) => sum + row.total, 0));
	const share = (total: number) => (grand === 0 ? 0 : (total / grand) * 100);
</script>

{#if rows.length > 0}
	<div class="flex flex-col gap-2.5">
		<div class="flex h-3 gap-px overflow-hidden rounded-full bg-surface-muted">
			{#each rows as row, index (row.provider)}
				<div
					class="{rankShade(index)} transition-opacity {dim(row.provider) ? 'opacity-20' : ''}"
					style="width: {share(row.total)}%"
					title="{labelFor(row.provider)}: {row.total}"
				></div>
			{/each}
		</div>

		<ul class="flex flex-wrap gap-x-4 gap-y-1.5">
			{#each rows as row, index (row.provider)}
				<li
					class="flex items-center gap-1.5 text-xs transition-opacity
						{dim(row.provider) ? 'opacity-40' : ''}"
				>
					<span aria-hidden="true" class="size-2 rounded-full {rankShade(index)}"></span>
					<span class="text-foreground/80">{labelFor(row.provider)}</span>
					<span class="text-muted-foreground tabular-nums">{share(row.total).toFixed(0)}%</span>
				</li>
			{/each}
		</ul>
	</div>
{/if}

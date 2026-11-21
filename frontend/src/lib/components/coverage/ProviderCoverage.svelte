<script lang="ts">
	import BarTrack from '$lib/components/charts/BarTrack.svelte';
	import ChartRow from '$lib/components/ui/ChartRow.svelte';
	import { LIST_FRAME } from '$lib/components/ui/table';
	import { MICRO } from '$lib/components/ui/typography';
	import { formatShare } from '$lib/utils/format';

	let {
		totals,
		capabilities,
		labelFor
	}: {
		/** How many capabilities each provider covers, richest first. */
		totals: Record<string, number>;
		/** The whole matrix, which every bar is a share of. */
		capabilities: number;
		labelFor: (provider: string) => string;
	} = $props();

	const headingId = $props.id();
</script>

<section aria-labelledby={headingId} class="flex flex-col gap-4 p-4 sm:p-5 {LIST_FRAME}">
	<div class="flex flex-col gap-0.5">
		<h2 id={headingId} class="text-base font-medium text-foreground">Provider coverage</h2>
		<p class={MICRO}>
			Share of all {capabilities} capabilities, as written in the integrations - not what your users have
			synced.
		</p>
	</div>

	<!-- Every provider, scaled to the whole matrix rather than to the leader: the
	     question is how much of it an integration covers. -->
	<ul class="flex flex-col gap-3 sm:gap-1.5">
		{#each Object.entries(totals) as [provider, count] (provider)}
			<li>
				<ChartRow label={labelFor(provider)} value={formatShare(count, capabilities)} stack>
					<BarTrack fraction={capabilities ? count / capabilities : 0} shade="bg-primary-soft" />
				</ChartRow>
			</li>
		{/each}
	</ul>
</section>

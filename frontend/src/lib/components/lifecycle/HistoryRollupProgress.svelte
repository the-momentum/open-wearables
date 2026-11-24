<script lang="ts">
	import type { HistoryRollup } from '$lib/lifecycle/types';
	import { formatNumber } from '$lib/utils/format';

	let { status }: { status: HistoryRollup } = $props();

	const pass = $derived(status.step === 'rollup_recent' ? 'the last 30 days' : 'the full history');
</script>

{#if status.state === 'done'}
	<p class="text-secondary-foreground">Done - every day of the history is rolled up.</p>
{:else}
	<p class="text-secondary-foreground">
		Running - {pass}: {formatNumber(status.sources_done)} of {formatNumber(status.sources_total)} data
		sources.
	</p>
	<p class="text-muted-foreground">
		The page shows where it was when it loaded; reload to follow it.
	</p>
{/if}

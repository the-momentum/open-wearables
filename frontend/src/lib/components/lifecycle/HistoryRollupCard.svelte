<script lang="ts">
	import History from '@lucide/svelte/icons/history';
	import Card from '$lib/components/ui/Card.svelte';
	import Switch from '$lib/components/ui/Switch.svelte';
	import type { HistoryRollup } from '$lib/lifecycle/types';
	import HistoryRollupProgress from './HistoryRollupProgress.svelte';

	let {
		status,
		rollup,
		enabled = $bindable(false)
	}: {
		status: HistoryRollup;
		/** The current rollup's switch as drafted: the history's needs it on. */
		rollup: boolean;
		enabled?: boolean;
	} = $props();
</script>

<Card
	icon={History}
	title="History rollup"
	description="Rolls up the days from before the rollup was switched on, once, in the background. Until it is done, summaries read those days from the samples, which is slower on large instances."
>
	{#snippet action()}
		<Switch
			bind:checked={enabled}
			label="Roll up the history"
			disabled={!rollup || status.state === 'done'}
		/>
	{/snippet}

	<div class="flex flex-col gap-2 text-sm">
		{#if status.state !== 'off'}
			<HistoryRollupProgress {status} />
		{:else if !rollup}
			<p class="text-muted-foreground">
				Needs rollup on: the days after it would not be rolled up.
			</p>
		{:else}
			<p class="text-muted-foreground">
				On a large instance this takes many hours and keeps the database busy while it runs. It can
				be switched off again and resumes where it stopped.
			</p>
		{/if}
	</div>
</Card>

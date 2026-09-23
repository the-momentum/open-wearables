<script lang="ts">
	import Play from '@lucide/svelte/icons/play';
	import Button from '$lib/components/ui/Button.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import ConfirmDialog from '$lib/components/ui/ConfirmDialog.svelte';
	import { MICRO } from '$lib/components/ui/typography';
	import type { ArchivalSettings } from '$lib/lifecycle/types';

	let {
		saved,
		unsaved,
		message,
		dispatched
	}: {
		/** What the job will actually use — the stored settings, never the draft. */
		saved: ArchivalSettings;
		unsaved: boolean;
		message?: string;
		dispatched?: boolean;
	} = $props();

	let open = $state(false);

	const idle = $derived(saved.archive_after_days === null && saved.delete_after_days === null);

	// No saving on the way, as the old dashboard did: with deletion on, that ran
	// a rule nobody had confirmed.
	const blocked = $derived(
		unsaved
			? 'Save your changes first — the job runs what is saved.'
			: idle
				? 'Nothing to run: archival and deletion are both off.'
				: null
	);
</script>

<Card
	icon={Play}
	title="Run now"
	description="Start the archival and deletion job instead of waiting for the daily schedule."
>
	<div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
		<p class={MICRO}>
			{#if message}
				<span class="text-danger">{message}</span>
			{:else if dispatched}
				Queued. It runs in the background, in batches — and space it frees is reused by new rows
				rather than handed back, so the sizes above may not drop.
			{:else}
				{blocked ?? 'Runs in the background; this page does not wait for it.'}
			{/if}
		</p>
		<Button variant="outline" disabled={blocked !== null} onclick={() => (open = true)}>
			<Play size={14} aria-hidden="true" />
			Run now
		</Button>
	</div>
</Card>

<ConfirmDialog
	bind:open
	title="Run the job now?"
	action="?/run"
	confirmLabel="Run now"
	busyLabel="Starting…"
	destructive={saved.delete_after_days !== null}
>
	{#if saved.archive_after_days !== null}
		Samples older than {saved.archive_after_days} days are rolled up into daily archive rows.
	{/if}
	{#if saved.delete_after_days !== null}
		Data older than {saved.delete_after_days} days is <strong>deleted permanently</strong>.
	{/if}
</ConfirmDialog>

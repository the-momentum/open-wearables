<script lang="ts">
	import Layers from '@lucide/svelte/icons/layers';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import SaveBar from '$lib/components/settings/SaveBar.svelte';
	import { invalid, LIMITS, policyOf, samePolicy, toFields } from '$lib/lifecycle/projection';
	import type { Lifecycle, Policy } from '$lib/lifecycle/types';
	import GrowthProjection from './GrowthProjection.svelte';
	import PolicyCard from './PolicyCard.svelte';
	import RunNow from './RunNow.svelte';
	import StorageOverview from './StorageOverview.svelte';

	let {
		lifecycle,
		message,
		dispatched
	}: { lifecycle: Lifecycle; message?: string; dispatched?: boolean } = $props();

	const saved = $derived(lifecycle.settings);

	// Re-derived when a save comes back.
	let rollupOn = $derived(saved.rollup_enabled);
	let retainOn = $derived(saved.delete_after_days !== null);
	// The days outlive their switch: a number typed while deletion is off is kept across saves,
	// and only a saved window replaces it.
	let retainDays = $state<number | null>(lifecycle.settings.delete_after_days ?? 365);
	$effect(() => {
		if (saved.delete_after_days !== null) retainDays = saved.delete_after_days;
	});

	const policy: Policy = $derived({
		rollup: rollupOn,
		retain: retainOn ? (retainDays ?? NaN) : null
	});

	const problem = $derived(invalid(policy));
	const unsaved = $derived(!samePolicy(policy, policyOf(saved)));

	// Mid-edit, the chart keeps the saved curve rather than one built from a blank.
	const drawn = $derived<Policy>(problem ? policyOf(saved) : policy);
</script>

<div class="flex flex-col gap-5">
	<StorageOverview storage={lifecycle.storage} />

	<GrowthProjection storage={lifecycle.storage} policy={drawn} />

	<div class="grid gap-5 lg:grid-cols-2">
		<PolicyCard
			icon={Layers}
			title="Rollup"
			description="Every night, the days whose samples changed are summed up into one row a day per series, and one per sleep or workout. Summaries read these rows; the samples stay until deletion removes them."
			toggle="Roll up samples"
			on="On - changed days are rolled up at 03:00 UTC."
			off="Off - the days that change are dropped, not kept for later: summaries and day reads for sources without provider day values stop at the last rolled-up day, and deletion removes samples for good."
			bind:enabled={rollupOn}
		/>

		<PolicyCard
			icon={Trash2}
			title="Deletion"
			description="Permanently removes samples older than the window, whole local days at a time. With rollup on, their days and sessions stay as aggregates. There is no undo."
			toggle="Delete old data"
			lead="Delete samples older than"
			off="Off - nothing is ever deleted."
			max={LIMITS.retain}
			bind:enabled={retainOn}
			bind:days={retainDays}
		/>
	</div>

	<RunNow {saved} {unsaved} {message} {dispatched} />
</div>

{#if unsaved}
	<SaveBar
		action="?/save"
		note={problem ?? 'Lifecycle policy changed'}
		disabled={problem !== null}
		payload={toFields(policy)}
	/>
{/if}

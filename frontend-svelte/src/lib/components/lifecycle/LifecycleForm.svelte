<script lang="ts">
	import Archive from '@lucide/svelte/icons/archive';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import SaveBar from '$lib/components/settings/SaveBar.svelte';
	import Alert from '$lib/components/ui/Alert.svelte';
	import {
		conflict,
		invalid,
		LIMITS,
		policyOf,
		samePolicy,
		toFields
	} from '$lib/lifecycle/projection';
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

	// Re-derived when a save comes back. The days outlive their switch, so
	// turning one off and on again keeps the number.
	let archiveOn = $derived(saved.archive_after_days !== null);
	let archiveDays = $derived<number | null>(saved.archive_after_days ?? 90);
	let retainOn = $derived(saved.delete_after_days !== null);
	let retainDays = $derived<number | null>(saved.delete_after_days ?? 365);

	const policy: Policy = $derived({
		archive: archiveOn ? (archiveDays ?? NaN) : null,
		retain: retainOn ? (retainDays ?? NaN) : null
	});

	const problem = $derived(invalid(policy));
	const warning = $derived(problem ? null : conflict(policy));
	const unsaved = $derived(!samePolicy(policy, policyOf(saved)));

	// Mid-edit, the chart keeps the saved curve rather than one built from a blank.
	const drawn = $derived<Policy>(problem ? policyOf(saved) : policy);
</script>

<div class="flex flex-col gap-5">
	<StorageOverview storage={lifecycle.storage} />

	<GrowthProjection storage={lifecycle.storage} policy={drawn} />

	<div class="grid gap-5 lg:grid-cols-2 lg:items-start">
		<PolicyCard
			icon={Archive}
			title="Archival"
			description="Rolls per-sample series older than the window into one row a day. Totals and averages survive; the individual samples do not."
			toggle="Archive old samples"
			lead="Archive data older than"
			off="Off — every sample is kept at full resolution."
			max={LIMITS.archive}
			bind:enabled={archiveOn}
			bind:days={archiveDays}
		/>

		<PolicyCard
			icon={Trash2}
			title="Deletion"
			description="Permanently removes data older than the window — archived rows when archival is on, live ones when it is not. There is no undo."
			toggle="Delete old data"
			lead="Delete data older than"
			off="Off — nothing is ever deleted."
			max={LIMITS.retain}
			bind:enabled={retainOn}
			bind:days={retainDays}
		/>
	</div>

	{#if warning}
		<Alert tone="warning">{warning}</Alert>
	{/if}

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

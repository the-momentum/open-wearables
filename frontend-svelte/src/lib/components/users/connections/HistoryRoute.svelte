<script lang="ts">
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import History from '@lucide/svelte/icons/history';
	import { enhance } from '$app/forms';
	import StatePlate from '$lib/components/ui/StatePlate.svelte';
	import {
		DEFAULT_RANGE,
		canSyncHistory,
		historyDelivery,
		historyLimitNote,
		historyRanges
	} from '$lib/connections/delivery';
	import type { Connection } from '$lib/connections/types';
	import { createSubmitFlag } from '$lib/utils/forms.svelte';
	import RoutePane from './RoutePane.svelte';

	let { connection, actionable }: { connection: Connection; actionable: boolean } = $props();

	const submit = createSubmitFlag();

	const startable = $derived(actionable && canSyncHistory(connection));
	const ranges = $derived(historyRanges(connection));
	const note = $derived(
		[startable ? historyDelivery(connection) + '.' : null, historyLimitNote(connection)]
			.filter(Boolean)
			.join(' ') || null
	);
	// A capped provider's last option is its cap, the only window it honours.
	const preselected = $derived(
		ranges.includes(DEFAULT_RANGE) ? DEFAULT_RANGE : ranges[ranges.length - 1]
	);
	const rangeId = $props.id();
</script>

<RoutePane icon={History} heading="Historical backfill" hint={note}>
	{#if startable}
		<form method="POST" action="?/syncHistory" use:enhance={submit.enhance} class="w-full">
			<input type="hidden" name="provider" value={connection.provider} />

			<!-- The wrapper owns the outline, the children round their own outer
			     corners: no overflow-hidden, so a keyboard outline is not clipped. -->
			<div class="flex w-full items-stretch rounded-lg border border-border">
				<div class="relative flex shrink-0 items-center">
					<label class="sr-only" for={rangeId}>History range</label>
					<select
						id={rangeId}
						name="days"
						value={preselected}
						class="min-h-11 appearance-none rounded-l-lg bg-transparent pr-7 pl-3 text-sm
							tabular-nums"
					>
						{#each ranges as days (days)}
							<option value={days}>{days} days</option>
						{/each}
					</select>
					<ChevronDown
						size={14}
						aria-hidden="true"
						class="pointer-events-none absolute right-2 text-muted-foreground"
					/>
				</div>

				<span aria-hidden="true" class="my-2 w-px shrink-0 bg-border"></span>

				<button
					type="submit"
					disabled={submit.submitting}
					class="min-h-11 flex-1 rounded-r-lg px-3 text-sm font-medium whitespace-nowrap
						transition-colors hover:bg-surface-muted disabled:opacity-50"
				>
					{submit.submitting ? 'Starting…' : 'Sync history'}
				</button>
			</div>
		</form>
	{:else}
		<StatePlate>{historyDelivery(connection)}</StatePlate>
	{/if}
</RoutePane>

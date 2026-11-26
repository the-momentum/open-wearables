<script lang="ts">
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import History from '@lucide/svelte/icons/history';
	import { enhance } from '$app/forms';
	import StatePlate from '$lib/components/ui/StatePlate.svelte';
	import { SELECT } from '$lib/components/ui/field';
	import { ICON } from '$lib/components/ui/icon';
	import {
		SDK_DELIVERY,
		DEFAULT_RANGE,
		canSyncHistory,
		historyDelivery,
		historyLimitNote,
		historyRanges
	} from '$lib/connections/delivery';
	import type { Connection } from '$lib/connections/types';
	import { cn } from '$lib/utils/cn';
	import { createSubmitFlag } from '$lib/utils/forms.svelte';
	import RoutePane from './RoutePane.svelte';

	let {
		connection,
		actionable,
		viaSdk = false
	}: { connection: Connection; actionable: boolean; viaSdk?: boolean } = $props();

	const submit = createSubmitFlag();

	const startable = $derived(actionable && canSyncHistory(connection));
	const ranges = $derived(historyRanges(connection));
	const note = $derived(
		viaSdk
			? SDK_DELIVERY.history.hint
			: [startable ? historyDelivery(connection) + '.' : null, historyLimitNote(connection)]
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
			     corners: no overflow-hidden, so a keyboard outline is not clipped.
			     The select's focus ring is drawn on the wrapper, so it follows the
			     rounded outline rather than squaring off mid-group. -->
			<div
				class="flex w-full items-stretch rounded-lg border border-border
					has-[select:focus-visible]:outline-2 has-[select:focus-visible]:outline-offset-2
					has-[select:focus-visible]:outline-ring"
			>
				<div class="relative flex shrink-0 items-center">
					<label class="sr-only" for={rangeId}>History range</label>
					<select
						id={rangeId}
						name="days"
						value={preselected}
						class={cn(
							SELECT.md,
							'h-auto min-h-11 rounded-r-none border-0 bg-transparent pl-3 text-sm focus-visible:outline-none'
						)}
					>
						{#each ranges as days (days)}
							<option value={days}>{days} days</option>
						{/each}
					</select>
					<ChevronDown
						size={ICON.xs}
						aria-hidden="true"
						class="pointer-events-none absolute right-2 text-muted-foreground"
					/>
				</div>

				<span aria-hidden="true" class="my-2 w-px shrink-0 bg-border"></span>

				<button
					type="submit"
					disabled={submit.submitting}
					class="min-h-11 flex-1 rounded-r-lg px-3 text-sm font-medium whitespace-nowrap
						transition-colors hover:bg-surface-muted focus-visible:rounded-l-lg disabled:opacity-50"
				>
					{submit.submitting ? 'Starting…' : 'Sync history'}
				</button>
			</div>
		</form>
	{:else}
		<StatePlate>{viaSdk ? SDK_DELIVERY.history.label : historyDelivery(connection)}</StatePlate>
	{/if}
</RoutePane>

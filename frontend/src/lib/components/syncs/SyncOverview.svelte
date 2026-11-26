<script lang="ts">
	import CircleAlert from '@lucide/svelte/icons/circle-alert';
	import CircleCheck from '@lucide/svelte/icons/circle-check';
	import CircleX from '@lucide/svelte/icons/circle-x';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';
	import type { Snippet } from 'svelte';
	import { ICON } from '$lib/components/ui/icon';
	import { LIST_FRAME } from '$lib/components/ui/table';
	import { TONE, TONE_COLOUR } from '$lib/components/ui/tone';
	import { MICRO } from '$lib/components/ui/typography';
	import type { overview } from '$lib/syncs/runs';
	import { DASH, formatNumber, formatPercent } from '$lib/utils/format';

	let {
		counts,
		children
	}: {
		counts: ReturnType<typeof overview>;
		/** The footer: how many runs from how many users, and what the window left out. */
		children: Snippet;
	} = $props();

	const tiles = $derived([
		{ icon: CircleCheck, label: 'Completed', value: counts.completed, tone: 'success' as const },
		{ icon: CircleAlert, label: 'Need a look', value: counts.attention, tone: 'warning' as const },
		{ icon: CircleX, label: 'Failed', value: counts.failed, tone: 'danger' as const },
		{ icon: LoaderCircle, label: 'Running now', value: counts.running, tone: 'primary' as const }
	]);
</script>

<section aria-label="Syncs in the window" class="overflow-hidden {LIST_FRAME}">
	<dl class="grid lg:grid-cols-4">
		{#each tiles as tile (tile.label)}
			<div
				class="grid grid-cols-[1fr_auto] items-center gap-2 border-border p-4 not-last:border-b
					lg:grid-cols-1 lg:p-5 lg:not-last:border-r lg:not-last:border-b-0"
			>
				<dt class="flex items-center gap-1.5 text-sm text-secondary-foreground">
					<span
						aria-hidden="true"
						class="grid size-8 shrink-0 place-items-center rounded-lg {TONE[tile.tone]}"
					>
						<tile.icon size={ICON.sm} />
					</span>
					{tile.label}
				</dt>
				<dd class="text-2xl font-medium text-foreground tabular-nums lg:text-3xl">
					{formatNumber(tile.value)}
				</dd>
				<dd class="col-span-2 flex items-center gap-2 lg:col-span-1">
					<span aria-hidden="true" class="h-1 flex-1 overflow-hidden rounded-full bg-surface-muted">
						<span
							class="block h-full rounded-full"
							style="width: {counts.total
								? (tile.value / counts.total) * 100
								: 0}%; background: {TONE_COLOUR[tile.tone]}"
						></span>
					</span>
					<span class="{MICRO} tabular-nums">
						{counts.total ? formatPercent(tile.value, counts.total) : DASH}
					</span>
				</dd>
			</div>
		{/each}
	</dl>

	<p class="flex min-h-10 items-center border-t border-border px-4 py-2 lg:px-5 {MICRO}">
		{@render children()}
	</p>
</section>

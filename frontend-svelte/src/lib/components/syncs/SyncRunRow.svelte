<script lang="ts">
	import Layers from '@lucide/svelte/icons/layers';
	import Badge from '$lib/components/ui/Badge.svelte';
	import ProviderMark from '$lib/components/providers/ProviderMark.svelte';
	import { isRunning, statusTone } from '$lib/syncs/format';
	import type { SyncRunSummary } from '$lib/syncs/types';
	import { formatRelativeTime } from '$lib/utils/datetime';
	import { humanise } from '$lib/utils/text';
	import SavedCounts from './SavedCounts.svelte';
	import SourceGlyph from './SourceGlyph.svelte';

	let { run, label }: { run: SyncRunSummary; label: string } = $props();

	const running = $derived(isRunning(run.status));

	const items = $derived(
		run.items_processed === null
			? null
			: run.items_total === null
				? String(run.items_processed)
				: `${run.items_processed}/${run.items_total}`
	);

	const saved = $derived(
		run.items_inserted != null || run.items_updated != null
			? { inserted: run.items_inserted ?? 0, updated: run.items_updated ?? 0 }
			: null
	);

	// At 100% it would only repeat the badge, and full width it outweighed it.
	const progress = $derived(running && run.progress !== null ? run.progress : null);
</script>

<li class="flex items-start gap-3 px-4 py-3 sm:px-5">
	<ProviderMark provider={run.provider} {label} size="sm" />

	<div class="min-w-0 flex-1">
		<div class="flex items-center gap-2">
			<span class="truncate text-sm text-foreground/90">{label}</span>
			<Badge tone={statusTone(run.status)}>
				{running ? humanise(run.stage) : humanise(run.status)}
			</Badge>
			<SourceGlyph source={run.source} />
		</div>

		{#if progress !== null}
			<div
				class="mt-1.5 h-1 w-full max-w-48 overflow-hidden rounded-full bg-surface-muted"
				role="progressbar"
				aria-valuenow={Math.round(progress * 100)}
				aria-valuemin="0"
				aria-valuemax="100"
				aria-label="Sync progress"
			>
				<div class="h-full rounded-full bg-primary/60" style="width: {progress * 100}%"></div>
			</div>
		{/if}

		{#if run.error}
			<p class="mt-0.5 truncate text-xs text-danger" title={run.error}>{run.error}</p>
		{:else if saved}
			<div class="mt-0.5 flex flex-wrap items-center gap-x-3 text-xs text-muted-foreground">
				<SavedCounts inserted={saved.inserted} updated={saved.updated} />
			</div>
		{:else if run.message}
			<p class="mt-0.5 truncate text-xs text-muted-foreground" title={run.message}>{run.message}</p>
		{/if}
	</div>

	<div class="flex shrink-0 flex-col items-end gap-0.5">
		<p class="text-xs whitespace-nowrap text-muted-foreground" title={run.last_update}>
			{formatRelativeTime(run.last_update)}
		</p>
		{#if items}
			<p
				class="flex items-center gap-1 text-xs text-muted-foreground/70 tabular-nums"
				title="Items processed"
			>
				<Layers size={12} aria-hidden="true" />
				{items}
			</p>
		{/if}
	</div>
</li>

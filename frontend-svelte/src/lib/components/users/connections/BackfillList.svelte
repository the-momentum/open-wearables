<script lang="ts">
	import Badge from '$lib/components/ui/Badge.svelte';
	import SavedCounts from '$lib/components/syncs/SavedCounts.svelte';
	import SourceGlyph from '$lib/components/syncs/SourceGlyph.svelte';
	import { formatDuration, formatWindow, statusTone } from '$lib/syncs/format';
	import type { SyncRun } from '$lib/syncs/types';
	import { formatRelativeTime } from '$lib/utils/datetime';
	import { humanise } from '$lib/utils/text';

	let { runs }: { runs: SyncRun[] } = $props();
</script>

<ul class="flex flex-col gap-2">
	{#each runs as run (run.run_key)}
		{@const covered = formatWindow(run.window_start, run.window_end)}
		{@const duration = formatDuration(run.started_at, run.ended_at)}
		<li class="rounded-lg border border-border bg-background px-3 py-2">
			<div class="flex flex-wrap items-center justify-between gap-2">
				<div class="flex items-center gap-2">
					<Badge tone={statusTone(run.status)}>{humanise(run.status)}</Badge>
					<SourceGlyph source={run.source} />
				</div>
				<span class="text-xs text-muted-foreground" title={run.started_at}>
					{formatRelativeTime(run.started_at)}
				</span>
			</div>

			<div class="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
				{#if covered}
					<span>Covered <span class="text-foreground/80">{covered}</span></span>
				{/if}
				<SavedCounts inserted={run.items_inserted} updated={run.items_updated} />
				{#if duration}
					<span>Took <span class="text-foreground/80">{duration}</span></span>
				{/if}
			</div>

			{#if run.error}
				<p class="mt-1.5 text-xs break-words text-danger">{run.error}</p>
			{/if}
		</li>
	{/each}
</ul>

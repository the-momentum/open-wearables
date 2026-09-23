<script lang="ts">
	import Database from '@lucide/svelte/icons/database';
	import Badge from '$lib/components/ui/Badge.svelte';
	import Skeleton from '$lib/components/ui/Skeleton.svelte';
	import Fact from '$lib/components/ui/Fact.svelte';
	import { CAPTION, MICRO } from '$lib/components/ui/typography';
	import { formatDuration, formatWindow, statusTone } from '$lib/syncs/format';
	import type { SyncRunDetail } from '$lib/syncs/types';
	import { DASH } from '$lib/utils/format';
	import { resource } from '$lib/utils/resource.svelte';
	import { humanise } from '$lib/utils/text';
	import SavedCounts from './SavedCounts.svelte';

	let { runId }: { runId: string } = $props();

	const fetched = resource<{ stored: SyncRunDetail | null }>(
		() => `/syncs/runs/${encodeURIComponent(runId)}`
	);
	const stored = $derived(fetched.current?.stored ?? null);
</script>

<div class="flex flex-col gap-3 rounded-lg border border-border/70 bg-surface-muted/30 p-3">
	<span class="inline-flex items-center gap-1.5 {CAPTION}">
		<Database size={12} aria-hidden="true" />
		Stored record
	</span>

	{#if !fetched.settled}
		<Skeleton class="h-12" />
	{:else if fetched.current === null}
		<p class="text-sm text-danger">Could not read the stored record. Try opening it again.</p>
	{:else if !stored}
		<!-- Live runs are left out of Postgres on purpose: one row per webhook and
		     per SDK batch would be hundreds a day for an active user. -->
		<p class="text-sm text-foreground/85">
			None — a live sync is only kept in the 24-hour buffer above, and leaves it with the rest.
		</p>
	{:else}
		<dl class="flex flex-wrap gap-x-6 gap-y-2 text-sm">
			<Fact label="Scope">{humanise(stored.scope)}</Fact>
			<Fact label="Data covered"
				>{formatWindow(stored.window_start, stored.window_end) ?? DASH}</Fact
			>
			<Fact label="Took">{formatDuration(stored.started_at, stored.ended_at) ?? DASH}</Fact>
			<Fact label="Saved">
				<span class="text-xs text-muted-foreground">
					<SavedCounts inserted={stored.items_inserted} updated={stored.items_updated} />
				</span>
			</Fact>
		</dl>

		{#if stored.data_types.length > 0}
			<!-- Per data type, because "partial" on a run means some of these failed,
			     and the run's own counts cannot say which. -->
			<ul class="divide-y divide-border/70 border-t border-border/70">
				{#each stored.data_types as type (type.data_type)}
					{@const covered = formatWindow(type.covered_start, type.covered_end)}
					<li class="flex flex-wrap items-center gap-x-3 gap-y-1 py-2 text-sm">
						<span class="min-w-0 flex-1 truncate text-foreground/90"
							>{humanise(type.data_type)}</span
						>
						<Badge tone={statusTone(type.status)}>{humanise(type.status)}</Badge>
						<span class="text-xs text-muted-foreground">
							<SavedCounts inserted={type.items_inserted} updated={type.items_updated} />
						</span>
						{#if covered}
							<span class="{MICRO} tabular-nums">{covered}</span>
						{/if}
						{#if type.attempt > 1}<span class={MICRO}>attempt {type.attempt}</span>{/if}
						{#if type.error}
							<p class="basis-full truncate text-xs text-danger" title={type.error}>
								{type.error_code ? `${type.error_code}: ` : ''}{type.error}
							</p>
						{/if}
					</li>
				{/each}
			</ul>
		{/if}
	{/if}
</div>

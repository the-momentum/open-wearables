<script lang="ts">
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import { resolve } from '$app/paths';
	import { togglesCard } from '$lib/components/events/accordion';
	import ProviderMark from '$lib/components/providers/ProviderMark.svelte';
	import CopyableId from '$lib/components/ui/CopyableId.svelte';
	import Fact from '$lib/components/ui/Fact.svelte';
	import { MICRO, MONO } from '$lib/components/ui/typography';
	import { formatDuration, isRunning, itemsLabel } from '$lib/syncs/format';
	import type { SyncRunSummary } from '$lib/syncs/types';
	import { formatDateTime, formatRelativeTime } from '$lib/utils/datetime';
	import { DASH } from '$lib/utils/format';
	import RunProgress from './RunProgress.svelte';
	import RunStatus from './RunStatus.svelte';
	import SourceGlyph from './SourceGlyph.svelte';
	import StoredRun from './StoredRun.svelte';

	let { run, label }: { run: SyncRunSummary; label: string } = $props();

	let open = $state(false);
	const panelId = $props.id();
	const running = $derived(isRunning(run.status));

	const took = $derived(
		formatDuration(run.started_at, run.ended_at) ?? (running ? 'still running' : DASH)
	);

	const toggle = (event: MouseEvent) => {
		if (togglesCard(event)) open = !open;
	};
</script>

<!-- The whole row opens it, as a card does; the user link and the header button
     are what the keyboard reaches. -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<li onclick={toggle} class="flex cursor-pointer flex-col gap-3 px-4 py-3 sm:px-5">
	<div class="flex items-start gap-3">
		<ProviderMark provider={run.provider} {label} size="sm" />

		<button
			type="button"
			data-accordion-toggle
			aria-expanded={open}
			aria-controls={panelId}
			class="flex min-w-0 flex-1 flex-col items-start gap-0.5 text-left"
		>
			<span class="flex flex-wrap items-center gap-2">
				<span class="text-sm text-foreground/90">{label}</span>
				<RunStatus {run} />
				<SourceGlyph source={run.source} />
			</span>
			{#if run.error}
				<span class="max-w-full truncate text-xs text-danger" title={run.error}>{run.error}</span>
			{:else if run.message}
				<span class="max-w-full truncate {MICRO}" title={run.message}>{run.message}</span>
			{/if}
			{#if running && run.progress !== null}
				<RunProgress value={run.progress} class="mt-1" />
			{/if}
		</button>

		<div class="flex shrink-0 flex-col items-end gap-0.5">
			<span class="{MICRO} whitespace-nowrap" title={formatDateTime(run.last_update)}>
				{formatRelativeTime(run.last_update)}
			</span>
			<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -->
			<a
				href={resolve(`/users/${run.user_id}`)}
				class="{MONO} text-muted-foreground transition-colors hover:text-primary"
				title="Open this user"
			>
				{run.user_id.slice(0, 8)}
			</a>
		</div>

		<ChevronDown
			size={14}
			aria-hidden="true"
			class="mt-1 shrink-0 text-muted-foreground transition-transform {open ? 'rotate-180' : ''}"
		/>
	</div>

	{#if open}
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div
			id={panelId}
			class="flex cursor-auto flex-col gap-3 pl-9"
			onclick={(event) => event.stopPropagation()}
		>
			<!-- What the 24-hour buffer knows, then what Postgres kept. -->
			<dl class="flex flex-wrap gap-x-6 gap-y-2 text-sm">
				<Fact label="Started">{formatDateTime(run.started_at)}</Fact>
				<Fact label="Took">{took}</Fact>
				<Fact label="Items">{itemsLabel(run) ?? DASH}</Fact>
				<Fact label="Run"><CopyableId value={run.run_id} label="Run ID" visible={12} /></Fact>
			</dl>
			{#if run.error}
				<p class="text-sm break-words text-danger">{run.error}</p>
			{/if}

			<StoredRun runId={run.run_id} />
		</div>
	{/if}
</li>

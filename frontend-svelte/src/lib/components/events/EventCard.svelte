<script lang="ts">
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import type { Component, Snippet } from 'svelte';
	import ProviderMark from '$lib/components/providers/ProviderMark.svelte';
	import { deviceIcon } from '$lib/providers/devices';
	import type { WorkoutSource } from '$lib/workouts/types';

	let {
		icon: Icon,
		source,
		providerLabel,
		title,
		when,
		metrics,
		details
	}: {
		icon: Component;
		source: WorkoutSource;
		providerLabel: string;
		title: Snippet;
		when: Snippet;
		metrics: Snippet;
		/** Rendered only once the card is open, so its own fetches wait for that. */
		details: Snippet;
	} = $props();

	let expanded = $state(false);
	const panelId = $props.id();

	/**
	 * The metrics open the card too, but they are text first: dragging across a
	 * value to copy it ends in a click, and that must not count as one.
	 */
	function toggleUnlessSelecting() {
		if (!document.getSelection()?.toString()) expanded = !expanded;
	}

	// The device is the useful half when one provider carries several: "Garmin"
	// twice tells an admin nothing, "Forerunner 265" tells them which watch.
	const device = $derived(source.device_name ?? source.device);
	const origin = $derived([providerLabel, device].filter(Boolean).join(' · '));
	const DeviceIcon = $derived(deviceIcon(source.device_type));
</script>

<article
	class="flex flex-col gap-3.5 rounded-xl border bg-surface p-4 transition-colors
		{expanded ? 'border-primary/30' : 'border-border'}"
>
	<!-- A heading wrapping the toggle is the accordion pattern: the card keeps a
	     place in the document outline, and only the header toggles, so the metrics
	     below stay selectable text rather than sitting inside a button. -->
	<h3>
		<button
			type="button"
			onclick={() => (expanded = !expanded)}
			aria-expanded={expanded}
			aria-controls={panelId}
			class="group flex w-full cursor-pointer items-start gap-3 text-left"
		>
			<span
				aria-hidden="true"
				class="grid size-9 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary"
			>
				<Icon size={18} />
			</span>

			<span class="flex min-w-0 flex-1 flex-col gap-0.5">
				{@render title()}
				{@render when()}
			</span>

			<!-- Narrow screens keep the mark and drop the words; the title holds them.
			     The icon belongs to the device, not the provider, and comes from
			     `device_type` — a ring must not be drawn as a watch. -->
			<span class="flex shrink-0 items-center gap-1.5" title={origin}>
				<ProviderMark provider={source.provider} label={providerLabel} size="sm" />
				<span class="hidden items-center gap-1 text-xs text-muted-foreground sm:inline-flex">
					{providerLabel}
					{#if device}
						<span aria-hidden="true" class="text-muted-foreground/40">·</span>
						<DeviceIcon size={12} aria-hidden="true" class="shrink-0 text-muted-foreground/60" />
						{device}
					{/if}
				</span>
				<!-- A bordered target, not a bare glyph: at the end of a long source
				     string a muted chevron reads as decoration, and nothing else on the
				     card says it opens. -->
				<span
					aria-hidden="true"
					class="grid size-7 shrink-0 place-items-center rounded-lg border border-border
						text-muted-foreground transition-colors group-hover:border-primary/40
						group-hover:bg-primary/10 group-hover:text-primary"
				>
					<ChevronDown size={15} class="transition-transform {expanded ? 'rotate-180' : ''}" />
				</span>
			</span>
		</button>
	</h3>

	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div onclick={toggleUnlessSelecting} class="cursor-pointer">
		{@render metrics()}
	</div>

	{#if expanded}
		<div id={panelId}>{@render details()}</div>
	{/if}
</article>

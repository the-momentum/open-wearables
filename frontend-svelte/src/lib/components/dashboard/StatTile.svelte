<script lang="ts">
	import type { Component } from 'svelte';
	import { TONE, type Tone } from '$lib/components/ui/tone';
	import { MICRO } from '$lib/components/ui/typography';
	import { cn } from '$lib/utils/cn';

	let {
		icon: Icon,
		label,
		value,
		note,
		parts,
		tone = 'primary'
	}: {
		icon: Component;
		label: string;
		value: string;
		/** A word about the figure itself — that it is an estimate, say. */
		note?: string;
		/**
		 * Always rendered, zero included: "0 archived" says the archive is empty,
		 * and leaving the row out says nothing at all.
		 */
		parts: { label: string; value: string }[];
		tone?: Tone;
	} = $props();
</script>

<div class="flex flex-col rounded-xl border border-border bg-surface p-4">
	<div class="flex items-start justify-between gap-2">
		<span class="truncate text-xs font-medium text-muted-foreground">{label}</span>
		<span
			aria-hidden="true"
			class={cn('grid size-8 shrink-0 place-items-center rounded-lg', TONE[tone])}
		>
			<Icon size={16} />
		</span>
	</div>

	<!-- Centred in the flexible middle, so tiles stay balanced against each other
	     however many sub-metrics each one has. -->
	<div class="flex flex-1 flex-wrap items-baseline justify-center gap-x-2 py-4">
		<span class="text-3xl font-semibold text-foreground tabular-nums">{value}</span>
		{#if note}<span class={MICRO}>{note}</span>{/if}
	</div>

	<dl class="flex border-t border-border pt-3">
		{#each parts as part (part.label)}
			<div class="flex flex-1 flex-col items-center gap-0.5 text-center">
				<dd class="text-sm font-semibold text-foreground tabular-nums">{part.value}</dd>
				<dt class="{MICRO} truncate">{part.label}</dt>
			</div>
		{/each}
	</dl>
</div>

<script lang="ts">
	import ArrowRight from '@lucide/svelte/icons/arrow-right';
	import type { Component } from 'svelte';
	import { formatLocalDay, localRange } from '$lib/utils/format';

	let {
		from,
		to,
		zoneOffset,
		fromIcon: FromIcon,
		toIcon: ToIcon,
		dateBy = 'from'
	}: {
		from: string;
		to: string;
		zoneOffset: string | null;
		/** Icons name the two ends where they mean something — bed and sunrise. */
		fromIcon?: Component;
		toIcon?: Component;
		/**
		 * Which end the date belongs to. A workout happened on the evening it
		 * started; a night belongs to the morning someone woke up in.
		 */
		dateBy?: 'from' | 'to';
	} = $props();

	const day = $derived(formatLocalDay(dateBy === 'to' ? to : from, zoneOffset));
	const range = $derived(localRange(from, to, zoneOffset));

	// The weekday belongs to whichever end the date did not come from. Marking the
	// end the date already names says nothing, and leaves the other end looking
	// like it happened earlier the same day.
	const marked = $derived(range.crosses ? (dateBy === 'to' ? 'from' : 'to') : null);
</script>

<!-- The date muted, the two clock times not: run together in one grey line they
     read as a single blur rather than as when to when. -->
<span class="flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
	<span>{day}</span>
	<span aria-hidden="true" class="text-muted-foreground/40">·</span>

	<span class="inline-flex items-center gap-1">
		{#if FromIcon}
			<FromIcon size={12} aria-hidden="true" class="text-muted-foreground/60" />
		{/if}
		<span class="text-foreground/80 tabular-nums">
			{#if marked === 'from'}<span class="text-muted-foreground">{range.fromDay}</span>{/if}
			{range.from}
		</span>
	</span>

	<ArrowRight size={12} aria-hidden="true" class="text-muted-foreground/40" />

	<span class="inline-flex items-center gap-1">
		{#if ToIcon}
			<ToIcon size={12} aria-hidden="true" class="text-muted-foreground/60" />
		{/if}
		<span class="text-foreground/80 tabular-nums">
			{#if marked === 'to'}<span class="text-muted-foreground">{range.toDay}</span>{/if}
			{range.to}
		</span>
		{#if range.utc}<span class="text-muted-foreground/70">UTC</span>{/if}
	</span>
</span>

<script lang="ts">
	import type { Component, Snippet } from 'svelte';
	import Hint from '$lib/components/ui/Hint.svelte';

	let {
		icon: Icon,
		heading,
		hint,
		children
	}: {
		icon: Component;
		heading: string;
		/** What the control below cannot say for itself. */
		hint?: string | null;
		children: Snippet;
	} = $props();
</script>

<!-- flex-wrap: the split control needs ~215px and a phone leaves under 200
     beside the heading, so it drops to its own line rather than overflowing. -->
<div
	class="flex min-w-0 flex-wrap items-center justify-between gap-x-3 gap-y-2 px-3 py-2.5
		sm:flex-col sm:justify-center sm:py-3"
>
	<p class="flex min-w-0 items-center gap-1.5 text-[10px] font-semibold tracking-wider uppercase">
		<Icon size={12} aria-hidden="true" class="shrink-0 text-muted-foreground/50" />
		<span class="text-muted-foreground/70">{heading}</span>
		{#if hint}
			<Hint label="{heading} details" text={hint} />
		{/if}
	</p>

	<div class="flex min-w-0 items-center justify-end gap-2 sm:w-full sm:justify-center">
		{@render children()}
	</div>
</div>

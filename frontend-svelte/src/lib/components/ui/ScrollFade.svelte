<script lang="ts">
	import type { Snippet } from 'svelte';
	import { cn } from '$lib/utils/cn';

	let {
		scroller = $bindable(),
		class: className,
		children
	}: {
		/** Bound so the caller can scroll something of its own into view. */
		scroller?: HTMLDivElement;
		class?: string;
		children: Snippet;
	} = $props();

	// Both true when everything fits, so the fades hide themselves without a
	// breakpoint knowing anything about the content.
	let atStart = $state(true);
	let atEnd = $state(true);

	function track() {
		if (!scroller) return;
		atStart = scroller.scrollLeft <= 1;
		atEnd = scroller.scrollLeft + scroller.clientWidth >= scroller.scrollWidth - 1;
	}

	$effect(track);
</script>

<svelte:window onresize={track} />

<div class="relative">
	<div bind:this={scroller} onscroll={track} class={cn('scroller flex overflow-x-auto', className)}>
		{@render children()}
	</div>

	<!-- Stops a pixel short of the bottom so a rule on the scroller stays whole. -->
	{#if !atStart}
		<div
			aria-hidden="true"
			class="pointer-events-none absolute top-0 bottom-px left-0 w-8 bg-gradient-to-r from-background to-transparent"
		></div>
	{/if}
	{#if !atEnd}
		<div
			aria-hidden="true"
			class="pointer-events-none absolute top-0 right-0 bottom-px w-8 bg-gradient-to-l from-background to-transparent"
		></div>
	{/if}
</div>

<style>
	/* No utility for this in Tailwind v4, and the bar would sit on the rule. */
	.scroller {
		scrollbar-width: none;
	}

	.scroller::-webkit-scrollbar {
		display: none;
	}
</style>

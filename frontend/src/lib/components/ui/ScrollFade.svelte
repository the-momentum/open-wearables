<script lang="ts">
	import ChevronLeft from '@lucide/svelte/icons/chevron-left';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
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

	// A mouse wheel only scrolls vertically and the bar is hidden, so it moves the strip sideways
	// while there is room, and leaves the page to scroll once the strip reaches its end
	function wheel(event: WheelEvent) {
		if (!scroller || Math.abs(event.deltaX) >= Math.abs(event.deltaY)) return;
		if (event.deltaY > 0 ? atEnd : atStart) return;
		event.preventDefault();
		scroller.scrollLeft += event.deltaY;
	}

	function step(direction: -1 | 1) {
		const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
		scroller?.scrollBy({
			left: direction * scroller.clientWidth * 0.8,
			behavior: reduced ? 'auto' : 'smooth'
		});
	}

	type Edge = 'left' | 'right';

	const EDGES = {
		left: { at: 'left-0', fade: 'bg-gradient-to-r', direction: -1, icon: ChevronLeft },
		right: { at: 'right-0', fade: 'bg-gradient-to-l', direction: 1, icon: ChevronRight }
	} as const;
</script>

<!-- A mouse has no swipe, so the edges also get arrows, on a fade wide enough to hide what
     sits under them. Out of the tab order: the keyboard reaches every item by tabbing to it. -->
{#snippet edge(side: Edge)}
	{@const { at, fade, direction, icon: Icon } = EDGES[side]}
	<!-- Stops a pixel short of the bottom so a rule on the scroller stays whole. -->
	<div
		aria-hidden="true"
		class={cn(
			'pointer-events-none absolute top-0 bottom-px w-8 from-background to-transparent pointer-fine:w-16 pointer-fine:from-40%',
			at,
			fade
		)}
	></div>
	<button
		type="button"
		tabindex="-1"
		aria-label="Scroll {side}"
		class={cn(
			'absolute top-1/2 hidden size-7 -translate-y-1/2 place-items-center text-muted-foreground transition-colors hover:text-foreground pointer-fine:grid',
			at
		)}
		onclick={() => step(direction)}
	>
		<Icon size={18} strokeWidth={2.5} aria-hidden="true" />
	</button>
{/snippet}

<svelte:window onresize={track} />

<div class="relative">
	<!-- Horizontal only: overflow-x alone makes the other axis scroll too, and a
	     pixel of overflow is enough for a sideways swipe to wobble it. -->
	<div
		bind:this={scroller}
		onscroll={track}
		onwheel={wheel}
		class={cn('scroller flex overflow-x-auto overflow-y-hidden overscroll-x-contain', className)}
	>
		{@render children()}
	</div>

	{#if !atStart}{@render edge('left')}{/if}
	{#if !atEnd}{@render edge('right')}{/if}
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

<script lang="ts">
	import type { Snippet } from 'svelte';
	import Info from '@lucide/svelte/icons/info';
	import { cn } from '$lib/utils/cn';
	import { ICON } from './icon';
	import { TOOLTIP } from './typography';

	let {
		label,
		text,
		align = 'right',
		trigger,
		children
	}: {
		label: string;
		/** Bubble content, when a plain sentence is all it needs. */
		text?: string;
		/** Which edge the bubble prefers to hang from; it still stays in the viewport. */
		align?: 'left' | 'right';
		/** Replaces the info icon. */
		trigger?: Snippet;
		children?: Snippet;
	} = $props();

	// The gap between trigger and bubble, the arrow's size and the margin kept
	// from the viewport's edge, in px.
	const GAP = 10;
	const ARROW = 6;
	const EDGE = 8;

	// The click is what makes it reachable on a phone, where :hover never fires.
	// No `title` on the trigger: the browser would draw a second tooltip over it.
	let pinned = $state(false);
	let hovered = $state(false);
	let focused = $state(false);
	// Escape hides a bubble that hover or focus opened, without moving focus
	// (WCAG 1.4.13); it comes back once the pointer or focus leaves and returns.
	let dismissed = $state(false);
	const open = $derived(!dismissed && (pinned || hovered || focused));
	// Below the trigger only when there is no room above it.
	let below = $state(false);

	let root = $state<HTMLElement>();
	let button = $state<HTMLButtonElement>();
	let bubble = $state<HTMLElement>();
	let arrow = $state<HTMLElement>();
	const bubbleId = $props.id();

	// Pinned by touch, so any tap elsewhere dismisses it. The trigger is inside
	// `root`, so tapping that still toggles rather than double-firing.
	$effect(() => {
		if (!pinned) return;

		const away = (event: Event) => {
			if (!root?.contains(event.target as Node)) pinned = false;
		};
		const escape = (event: KeyboardEvent) => {
			if (event.key === 'Escape') pinned = false;
		};

		document.addEventListener('pointerdown', away);
		document.addEventListener('keydown', escape);
		return () => {
			document.removeEventListener('pointerdown', away);
			document.removeEventListener('keydown', escape);
		};
	});

	// In the top layer, so no card's `overflow` clips it. Out of flow, it is
	// placed by hand and follows the trigger while anything scrolls.
	function place() {
		if (!button || !bubble || !arrow) return;
		const anchor = button.getBoundingClientRect();
		const { width, height } = bubble.getBoundingClientRect();

		below = anchor.top - GAP - height < EDGE;
		const top = below ? anchor.bottom + GAP : anchor.top - GAP - height;
		const preferred = align === 'right' ? anchor.right - width : anchor.left;
		const left = Math.max(EDGE, Math.min(preferred, window.innerWidth - width - EDGE));
		const centre = anchor.left + anchor.width / 2 - left;

		bubble.style.top = `${top}px`;
		bubble.style.left = `${left}px`;
		arrow.style.left = `${Math.max(ARROW, Math.min(centre, width - ARROW)) - ARROW}px`;
	}

	$effect(() => {
		if (!open || !bubble?.isConnected) return;

		bubble.showPopover();
		place();
		window.addEventListener('scroll', place, { capture: true, passive: true });
		window.addEventListener('resize', place);
		return () => {
			if (bubble?.matches(':popover-open')) bubble.hidePopover();
			window.removeEventListener('scroll', place, { capture: true });
			window.removeEventListener('resize', place);
		};
	});
</script>

<span bind:this={root} class="inline-flex align-middle">
	<button
		bind:this={button}
		type="button"
		onclick={() => {
			pinned = !pinned;
			dismissed = false;
		}}
		onkeydown={(event) => {
			if (event.key === 'Escape') dismissed = true;
		}}
		onpointerenter={(event) => {
			// A tap fires enter and leave around its click: pinning is the click's.
			if (event.pointerType !== 'touch') hovered = true;
		}}
		onpointerleave={() => {
			hovered = false;
			dismissed = false;
		}}
		onfocus={(event) => (focused = event.currentTarget.matches(':focus-visible'))}
		onblur={() => {
			focused = false;
			dismissed = false;
		}}
		aria-describedby={bubbleId}
		aria-label={label}
		class={cn(
			'transition-colors',
			trigger
				? 'cursor-default rounded-full'
				: 'grid size-4 place-items-center rounded-full text-muted-foreground/50 hover:text-muted-foreground'
		)}
	>
		{#if trigger}
			{@render trigger()}
		{:else}
			<Info size={ICON.xs} aria-hidden="true" />
		{/if}
	</button>

	<!-- The arrow stays on the trigger's centre wherever the bubble ends up. -->
	<span
		bind:this={bubble}
		id={bubbleId}
		role="tooltip"
		popover="manual"
		class={cn(
			`pointer-events-none fixed inset-auto m-0 w-max max-w-60 overflow-visible border-0
			font-sans font-normal tracking-normal normal-case`,
			TOOLTIP
		)}
	>
		<span
			bind:this={arrow}
			aria-hidden="true"
			class={cn(
				'absolute border-x-6 border-x-transparent',
				below ? 'bottom-full border-b-6 border-b-inverted' : 'top-full border-t-6 border-t-inverted'
			)}
		></span>
		{#if children}
			{@render children()}
		{:else}
			{text}
		{/if}
	</span>
</span>

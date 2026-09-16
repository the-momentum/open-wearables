<script lang="ts">
	import type { Snippet } from 'svelte';
	import Info from '@lucide/svelte/icons/info';
	import { cn } from '$lib/utils/cn';

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
		/** Which edge the bubble hangs from, so it stays inside its card. */
		align?: 'left' | 'right';
		/** Replaces the info icon. */
		trigger?: Snippet;
		children?: Snippet;
	} = $props();

	// The click is what makes it reachable on a phone, where :hover never fires.
	// No `title` on the trigger: the browser would draw a second tooltip over it.
	let pinned = $state(false);
	let root = $state<HTMLElement>();
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
</script>

<span bind:this={root} class="relative inline-flex align-middle">
	<button
		type="button"
		onclick={() => (pinned = !pinned)}
		aria-describedby={bubbleId}
		aria-label={label}
		class={cn(
			'peer transition-colors',
			trigger
				? 'cursor-default'
				: 'grid size-4 place-items-center rounded-full text-muted-foreground/50 hover:text-muted-foreground'
		)}
	>
		{#if trigger}
			{@render trigger()}
		{:else}
			<Info size={12} aria-hidden="true" />
		{/if}
	</button>

	<span
		id={bubbleId}
		role="tooltip"
		class={cn(
			`pointer-events-none absolute top-full z-20 mt-1 w-max max-w-52 rounded-lg border
			border-border bg-surface px-2.5 py-1.5 text-[11px] leading-snug font-normal
			tracking-normal text-foreground/90 normal-case shadow-lg
			peer-hover:visible peer-focus-visible:visible`,
			align === 'right' ? 'right-0' : 'left-0',
			pinned ? 'visible' : 'invisible'
		)}
	>
		{#if children}
			{@render children()}
		{:else}
			{text}
		{/if}
	</span>
</span>

<script lang="ts">
	import Info from '@lucide/svelte/icons/info';

	let { text, label }: { text: string; label: string } = $props();

	// The click is what makes it reachable on a phone, where :hover never fires.
	// No `title` on the trigger: the browser would draw a second tooltip over it.
	let pinned = $state(false);
	const bubbleId = $props.id();
</script>

<span class="relative inline-flex align-middle">
	<button
		type="button"
		onclick={() => (pinned = !pinned)}
		aria-describedby={bubbleId}
		aria-label={label}
		class="peer grid size-4 place-items-center rounded-full text-muted-foreground/50
			transition-colors hover:text-muted-foreground"
	>
		<Info size={12} aria-hidden="true" />
	</button>

	<!-- Opens leftwards: every hint icon sits in the right half of its pane, so
	     anchoring left spilled the bubble over the neighbouring card. -->
	<span
		id={bubbleId}
		role="tooltip"
		class="pointer-events-none absolute top-full right-0 z-20 mt-1 w-max max-w-52 rounded-lg border
			border-border bg-surface px-2.5 py-1.5 text-[11px] leading-snug font-normal
			tracking-normal text-foreground/90 normal-case shadow-lg
			peer-hover:visible peer-focus-visible:visible
			{pinned ? 'visible' : 'invisible'}"
	>
		{text}
	</span>
</span>

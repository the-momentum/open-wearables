<script lang="ts">
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import type { Component, Snippet } from 'svelte';

	let {
		icon: Icon,
		title,
		when,
		aside,
		metrics,
		details
	}: {
		/** Absent where the rows inside carry the icons instead. */
		icon?: Component;
		title: Snippet;
		/** A second heading line, where the title does not say when. */
		when?: Snippet;
		/** What sits before the chevron — where a record came from, usually. */
		aside: Snippet;
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
			{#if Icon}
				<span
					aria-hidden="true"
					class="grid size-9 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary"
				>
					<Icon size={18} />
				</span>
			{/if}

			<span class="flex min-w-0 flex-1 flex-col gap-0.5">
				{@render title()}
				{@render when?.()}
			</span>

			<span class="flex shrink-0 items-center gap-1.5">
				{@render aside()}
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

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
	 * The whole card opens it, not just the header: the padding and the gaps
	 * between the rows are card too, and a click that lands there and does
	 * nothing reads as a broken control.
	 *
	 * Two things are not that click. A control the card carries — an edit button,
	 * a link to somewhere else — does its own job and must not fold the card
	 * underneath it. And a card is text first: dragging across a value to copy it
	 * ends in a click, which must not count as one either.
	 */
	function toggleUnlessBusy(event: MouseEvent) {
		const target = event.target as Element | null;
		const control = target?.closest('a, button, input, select, textarea, label');

		if (control && !control.matches('[data-accordion-toggle]')) return;
		if (!document.getSelection()?.toString()) expanded = !expanded;
	}
</script>

<!-- The heading button below is what assistive tech and the keyboard drive; this
     handler only widens the pointer target to the whole card. -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<article
	onclick={toggleUnlessBusy}
	class="flex cursor-pointer flex-col gap-3.5 rounded-xl border bg-surface p-4 transition-colors
		{expanded ? 'border-primary/30' : 'border-border'}"
>
	<!-- A heading wrapping the toggle is the accordion pattern: the card keeps a
	     place in the document outline, and only the header toggles, so the metrics
	     below stay selectable text rather than sitting inside a button. -->
	<h3>
		<button
			type="button"
			data-accordion-toggle
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

	<div>{@render metrics()}</div>

	<!-- The panel is its own thing: selecting a value or following a link inside
	     it must not fold the card away underneath. -->
	{#if expanded}
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div id={panelId} class="cursor-auto" onclick={(event) => event.stopPropagation()}>
			{@render details()}
		</div>
	{/if}
</article>

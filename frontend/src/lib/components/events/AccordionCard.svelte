<script lang="ts">
	import ExpandChevron from '$lib/components/ui/ExpandChevron.svelte';
	import { ICON, ICON_TILE } from '$lib/components/ui/icon';
	import type { Component, Snippet } from 'svelte';
	import { togglesCard } from './accordion';

	let {
		icon: Icon,
		title,
		when,
		aside,
		control,
		metrics,
		details
	}: {
		/** Absent where the rows inside carry the icons instead. */
		icon?: Component;
		title: Snippet;
		/** A second heading line, where the title does not say when. */
		when?: Snippet;
		/** What sits before the chevron - where a record came from, usually. Part of the toggle's name. */
		aside?: Snippet;
		/**
		 * A control of the card's own - a switch, say. Outside the header button,
		 * because a button inside a button is not HTML: the parser closes the
		 * first at the second, so the server's markup arrives already broken.
		 */
		control?: Snippet;
		/** Always visible under the header; a form section has none. */
		metrics?: Snippet;
		/** Rendered only once the card is open, so its own fetches wait for that. */
		details: Snippet;
	} = $props();

	let expanded = $state(false);
	const panelId = $props.id();

	const toggleUnlessBusy = (event: MouseEvent) => {
		if (togglesCard(event)) expanded = !expanded;
	};
</script>

<!-- The heading button below is what assistive tech and the keyboard drive; this
     handler only widens the pointer target to the whole card. -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<article
	onclick={toggleUnlessBusy}
	class="flex cursor-pointer flex-col rounded-xl border border-border bg-card"
>
	<div class="flex flex-col gap-3.5 p-4">
		<!-- A heading wrapping the toggle is the accordion pattern: the card keeps a
		     place in the document outline, and only the header toggles, so the metrics
		     below stay selectable text rather than sitting inside a button. -->
		<div class="group flex items-start gap-2 sm:items-center">
			<h3 class="min-w-0 flex-1">
				<button
					type="button"
					data-accordion-toggle
					aria-expanded={expanded}
					aria-controls={panelId}
					class="flex w-full cursor-pointer items-start gap-3 text-left sm:items-center"
				>
					{#if Icon}
						<span aria-hidden="true" class={ICON_TILE}>
							<Icon size={ICON.md} />
						</span>
					{/if}

					<span class="flex min-w-0 flex-1 flex-col gap-0.5">
						{@render title()}
						{@render when?.()}
					</span>

					{#if aside}
						<span class="flex shrink-0 items-center gap-1.5">{@render aside()}</span>
					{/if}
				</button>
			</h3>

			{@render control?.()}

			<!-- Outside the button so a control can sit between them; a click on it
			     still reaches the card. Boxed, because a bare chevron after a long
			     source string reads as decoration. -->
			<ExpandChevron open={expanded} boxed />
		</div>

		{#if metrics}<div>{@render metrics()}</div>{/if}
	</div>

	<!-- Selecting a value or following a link inside the panel must not fold the
	     card away underneath. -->
	{#if expanded}
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div
			id={panelId}
			class="cursor-auto border-t border-border p-4"
			onclick={(event) => event.stopPropagation()}
		>
			{@render details()}
		</div>
	{/if}
</article>

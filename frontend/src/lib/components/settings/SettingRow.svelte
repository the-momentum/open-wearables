<script lang="ts">
	import type { Snippet } from 'svelte';
	import { MICRO } from '$lib/components/ui/typography';

	let {
		lead,
		title,
		meta,
		actions
	}: {
		/** A glyph or a logo, where the row has one. */
		lead?: Snippet;
		/** The name, and any badge that belongs beside it. */
		title: Snippet;
		/** The small print under the name. */
		meta?: Snippet;
		actions: Snippet;
	} = $props();
</script>

<!-- Wraps rather than scrolls: on a phone the actions drop under the name
     instead of sitting behind a horizontal scrollbar. -->
<div class="flex flex-wrap items-center gap-x-3 gap-y-2 py-3">
	{@render lead?.()}

	<div class="flex min-w-0 flex-1 flex-col gap-1">
		<div class="flex flex-wrap items-center gap-2">{@render title()}</div>
		{#if meta}
			<div class="flex flex-wrap items-center gap-x-2 gap-y-1 {MICRO}">{@render meta()}</div>
		{/if}
	</div>

	<div class="flex shrink-0 items-center gap-1.5">{@render actions()}</div>
</div>

<script lang="ts">
	import type { Snippet } from 'svelte';
	import { MICRO } from '$lib/components/ui/typography';
	import { cn } from '$lib/utils/cn';

	let {
		lead,
		title,
		meta,
		actions,
		below = false
	}: {
		/** A glyph or a logo, where the row has one. */
		lead?: Snippet;
		/** The name, and any badge that belongs beside it. */
		title: Snippet;
		/** The small print under the name. */
		meta?: Snippet;
		actions: Snippet;
		/** A phone lays the actions on a line of their own, under the small print. */
		below?: boolean;
	} = $props();
</script>

<!-- A grid, so a long name truncates rather than pushing the actions off. -->
<div
	class={cn(
		'grid items-center gap-x-3 gap-y-2 py-3 sm:gap-y-0.5',
		lead ? 'grid-cols-[auto_minmax(0,1fr)_auto]' : 'grid-cols-[minmax(0,1fr)_auto]'
	)}
>
	{#if lead}
		<div class={cn(meta && 'sm:row-span-2')}>{@render lead()}</div>
	{/if}

	<div class={cn('flex min-w-0 flex-wrap items-center gap-2', below && 'max-sm:col-span-2')}>
		{@render title()}
	</div>

	<div
		class={cn(
			'flex items-center justify-end gap-1.5',
			meta && 'sm:row-span-2',
			below && 'max-sm:col-span-full max-sm:row-start-3 max-sm:justify-start'
		)}
	>
		{@render actions()}
	</div>

	{#if meta}
		<div
			class={cn(
				'col-span-2 flex flex-wrap items-center gap-x-2.5 gap-y-1 sm:col-span-1',
				lead && 'col-start-2',
				MICRO
			)}
		>
			{@render meta()}
		</div>
	{/if}
</div>

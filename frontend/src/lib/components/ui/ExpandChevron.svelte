<script lang="ts">
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import { cn } from '$lib/utils/cn';
	import { ICON } from './icon';

	let {
		open,
		size,
		boxed = false,
		class: className
	}: {
		open: boolean;
		size?: number;
		/** The design's ExpandButton: a bordered square that lights up while its
		 *  `group` (the card or row that opens) is hovered. Bare, it is the quiet
		 *  chevron at the end of a list row. */
		boxed?: boolean;
		class?: string;
	} = $props();

	const turn = $derived(cn('shrink-0 transition-transform', open && 'rotate-180'));
</script>

{#if boxed}
	<span
		aria-hidden="true"
		class={cn(
			`grid size-9 shrink-0 place-items-center rounded-lg border border-border text-foreground
			transition-colors group-hover:border-primary/40 group-hover:bg-primary/10
			group-hover:text-primary`,
			className
		)}
	>
		<ChevronDown size={size ?? ICON.sm} class={turn} />
	</span>
{:else}
	<ChevronDown
		size={size ?? ICON.xs}
		aria-hidden="true"
		class={cn(turn, 'text-muted-foreground', className)}
	/>
{/if}

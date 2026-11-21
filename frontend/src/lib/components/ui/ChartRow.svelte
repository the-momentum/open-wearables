<script lang="ts">
	import type { Snippet } from 'svelte';
	import { cn } from '$lib/utils/cn';

	let {
		label = '',
		value = '',
		hoverable = false,
		stack = false,
		children
	}: {
		label?: string;
		value?: string | number;
		/** Lifts the label and value while the pointer is on the row. */
		hoverable?: boolean;
		/** On a phone the label and value share a line above a full-width bar. */
		stack?: boolean;
		children: Snippet;
	} = $props();

	const shift = $derived(hoverable ? 'transition-colors group-hover:text-foreground' : '');
</script>

<!-- One place for the three column widths: an axis row has to line up with the
     data rows beneath it, and keeping the numbers in both drifted once already. -->
<div
	class={cn(
		'flex items-center gap-3',
		stack && 'max-sm:grid max-sm:grid-cols-[minmax(0,1fr)_auto] max-sm:gap-y-1',
		hoverable && 'group'
	)}
>
	<span
		class={cn(
			'w-20 shrink-0 truncate text-xs text-secondary-foreground sm:w-32',
			stack && 'max-sm:w-auto',
			shift
		)}
		title={label || undefined}
	>
		{label}
	</span>

	<div class={cn('min-w-0 flex-1', stack && 'max-sm:order-last max-sm:col-span-2')}>
		{@render children()}
	</div>

	<span
		class={cn(
			'w-14 shrink-0 text-right text-xs whitespace-nowrap text-muted-foreground tabular-nums sm:w-20',
			stack && 'max-sm:w-auto',
			shift
		)}
	>
		{value}
	</span>
</div>

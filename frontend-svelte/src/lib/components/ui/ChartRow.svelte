<script lang="ts">
	import type { Snippet } from 'svelte';
	import { cn } from '$lib/utils/cn';

	let {
		label = '',
		value = '',
		hoverable = false,
		children
	}: {
		label?: string;
		value?: string | number;
		/** Lifts the label and value while the pointer is on the row. */
		hoverable?: boolean;
		children: Snippet;
	} = $props();

	const shift = $derived(hoverable ? 'transition-colors group-hover:text-foreground' : '');
</script>

<!-- One place for the three column widths: an axis row has to line up with the
     data rows beneath it, and keeping the numbers in both drifted once already. -->
<div class={cn('flex items-center gap-3', hoverable && 'group')}>
	<span
		class={cn('w-20 shrink-0 truncate text-xs text-foreground/80 sm:w-32', shift)}
		title={label || undefined}
	>
		{label}
	</span>

	<div class="min-w-0 flex-1">{@render children()}</div>

	<span
		class={cn('w-12 shrink-0 text-right text-xs text-muted-foreground tabular-nums sm:w-14', shift)}
	>
		{value}
	</span>
</div>

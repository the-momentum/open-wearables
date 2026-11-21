<script lang="ts">
	import { cn } from '$lib/utils/cn';

	let {
		fraction,
		shade = 'bg-primary/40',
		class: className
	}: {
		/** How much of the track is filled, 0 to 1. */
		fraction: number;
		/** The design's ChartRow fill unless the row means something of its own. */
		shade?: string;
		class?: string;
	} = $props();
</script>

<span class={cn('block h-2.5 overflow-hidden rounded-full bg-surface-muted', className)}>
	<span
		aria-hidden="true"
		class="block h-full rounded-full transition-[width] duration-300 {shade}"
		style:width="{fraction * 100}%"
	></span>
</span>

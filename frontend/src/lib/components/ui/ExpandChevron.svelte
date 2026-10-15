<script lang="ts">
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import { cn } from '$lib/utils/cn';

	let {
		open,
		size = 14,
		class: className
	}: { open: boolean; size?: number; class?: string } = $props();
</script>

<ChevronDown
	{size}
	aria-hidden="true"
	class={cn('shrink-0 text-muted-foreground transition-transform', open && 'rotate-180', className)}
/>

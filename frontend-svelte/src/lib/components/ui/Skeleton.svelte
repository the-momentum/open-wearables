<script lang="ts">
	import { cn } from '$lib/utils/cn';

	/** Holds the space its content will take, so nothing jumps when it arrives. */
	let { class: className }: { class?: string } = $props();
</script>

<div aria-hidden="true" class={cn('animate-pulse rounded-lg bg-surface-muted/60', className)}></div>

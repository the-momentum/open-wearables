<script lang="ts">
	import type { Snippet } from 'svelte';
	import { cn } from '$lib/utils/cn';

	export type BadgeTone = 'success' | 'warning' | 'danger' | 'info' | 'neutral';

	let {
		tone = 'neutral',
		class: className,
		children
	}: { tone?: BadgeTone; class?: string; children: Snippet } = $props();

	const TONE = {
		success: 'bg-success/12 text-success',
		warning: 'bg-warning/15 text-warning',
		danger: 'bg-danger/12 text-danger',
		info: 'bg-primary/12 text-primary',
		neutral: 'bg-surface-muted text-muted-foreground'
	} as const;
</script>

<span
	class={cn(
		'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap',
		TONE[tone],
		className
	)}
>
	{@render children()}
</span>

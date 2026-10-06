<script lang="ts">
	import type { Snippet } from 'svelte';
	import { cn } from '$lib/utils/cn';
	import { TONE, type Tone } from './tone';

	let {
		tone = 'neutral',
		class: className,
		children
	}: { tone?: Tone; class?: string; children: Snippet } = $props();
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
